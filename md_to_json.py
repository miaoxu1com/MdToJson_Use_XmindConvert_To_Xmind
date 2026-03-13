"""
MD文件解析为思维导图JSON格式脚本
解析测试用例MD文件，生成指定格式的JSON数据

JSON结构规范：
{
  "title": "思维导图名称",
  "topic_node": {
    "title": "Root",
    "id": "root-id",
    "notes": "节点的可选备注",
    "labels": ["标签1", "标签2"],
    "children": [...]
  },
  "detached_nodes": [],
  "relations": []
}

解析规则：
- MD文件的需求名称为根节点（Root）
- MD文件中以"TC"开头的标题（如 ### TC001）是根节点的子节点（测试用例）
- 用例名称的子节点是测试步骤
- 测试步骤的子节点是预期结果
"""

import re
import json
import uuid
from pathlib import Path
from typing import List, Dict, Optional


def generate_id() -> str:
    """生成唯一ID"""
    return str(uuid.uuid4())[:8]


class TestCase:
    """测试用例数据结构"""
    def __init__(self, case_id: str, title: str, priority: str, module: str,
                 pre_condition: str, steps: str, expected_result: str):
        self.case_id = case_id
        self.title = title
        self.priority = priority
        self.module = module
        self.pre_condition = pre_condition
        self.steps = steps
        self.expected_result = expected_result


def parse_markdown_to_cases(md_path: str) -> Dict[str, List[TestCase]]:
    """
    解析MD文件，按测试用例标题（TC开头）组织数据

    Args:
        md_path: MD文件路径

    Returns:
        按测试用例ID分组的数据字典
    """
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 需求信息
    request_info = {}
    for field, label in [
        ("request_no", "需求编号"),
        ("request_name", "需求名称"),
        ("owner", "需求负责人"),
        ("department", "涉及部门")
    ]:
        match = re.search(fr'{label}\|(.+?)\|', content)
        if match:
            request_info[field] = match.group(1).strip()

    # 结果字典
    result = {
        "request_info": request_info,
        "cases_by_id": {},
        "root_title": request_info.get("request_name", "测试用例脑图")
    }

    # 添加需求编号到标题
    if request_info.get("request_no"):
        result["root_title"] = f"{result['root_title']}（{request_info['request_no']}）"

    # 解析策略：从表格中提取测试用例
    # 查找所有表格，然后从表格中提取TC-xxx格式的测试用例
    case_sections = []
    
    # 查找所有表格
    lines = content.split('\n')
    in_table = False
    current_table = []
    
    for line in lines:
        stripped = line.strip()
        # 检查是否是表格行（包含|）
        if '|' in line:
            in_table = True
            current_table.append(line)
        else:
            # 如果之前在表格中，现在遇到非表格行，说明表格结束
            if in_table:
                case_sections.append('\n'.join(current_table))
                current_table = []
                in_table = False
    
    # 处理最后一个表格
    if in_table and current_table:
        case_sections.append('\n'.join(current_table))
    
    # 从表格中提取测试用例
    parsed_cases = []
    
    for table_content in case_sections:
        # 按行分割表格
        table_lines = table_content.split('\n')
        header_line = None
        data_lines = []
        
        for line in table_lines:
            if '|' in line:
                stripped = line.strip()
                # 跳过表格分割线
                if not re.match(r'^\|\s*-+\s*\|', stripped):
                    if '用例ID' in line or '测试场景' in line:
                        header_line = line
                    else:
                        data_lines.append(line)
        
        # 提取测试用例
        if header_line and data_lines:
            for data_line in data_lines:
                # 分割表格行
                cells = [cell.strip() for cell in data_line.split('|') if cell.strip()]
                if len(cells) >= 5:
                    # 提取各字段
                    case_id = cells[0]
                    # 只处理TC-xxx格式的用例ID
                    if re.match(r'^TC-\d+$', case_id):
                        case_title = cells[1]  # 测试场景
                        pre_condition = cells[2]  # 前置条件
                        steps = cells[3]  # 测试步骤
                        expected_result = cells[4]  # 预期结果
                        priority = cells[5] if len(cells) > 5 else ""
                        
                        parsed_cases.append({
                            'case_id': case_id,
                            'title': case_title,
                            'priority': priority,
                            'pre_condition': pre_condition,
                            'steps': steps,
                            'expected_result': expected_result
                        })

    # 处理解析后的测试用例
    for case_data in parsed_cases:
        case_id = case_data['case_id']
        case_title = case_data['title']
        priority = case_data['priority']
        pre_condition = case_data['pre_condition']
        steps = case_data['steps']
        expected_result = case_data['expected_result']
        
        # 清理HTML标签和多余字符
        if steps:
            steps = re.sub(r'<[^>]+>', '', steps)
            steps = re.sub(r'&lt;|&gt;|&amp;', lambda m: {'&lt;': '<', '&gt;': '>', '&amp;': '&'}[m.group()], steps)
            steps = steps.replace('<br>', ' ').replace('<br/>', ' ')
            steps = re.sub(r'\s+', ' ', steps).strip()
            # 处理转义的引号
            steps = steps.replace('\\"', '"')

        if expected_result:
            expected_result = re.sub(r'<[^>]+>', '', expected_result)
            expected_result = re.sub(r'&lt;|&gt;|&amp;', lambda m: {'&lt;': '<', '&gt;': '>', '&amp;': '&'}[m.group()], expected_result)
            expected_result = re.sub(r'\s+', ' ', expected_result).strip()
            # 处理转义的引号
            expected_result = expected_result.replace('\\"', '"')

        test_case = TestCase(
            case_id=case_id.upper(),
            title=case_title,
            priority=priority,
            module="",  # 原表格中没有模块字段
            pre_condition=pre_condition,
            steps=steps,
            expected_result=expected_result
        )

        result["cases_by_id"][case_id.upper()] = test_case

    return result


def create_node(title: str, node_id: str = None, notes: str = None,
                labels: List[str] = None) -> Dict:
    """
    创建一个基础节点

    Args:
        title: 节点标题
        node_id: 节点ID（可选）
        notes: 备注信息（可选）
        labels: 标签列表（可选）

    Returns:
        节点字典
    """
    return {
        "title": title,
        "id": node_id or generate_id(),
        "notes": notes or "",
        "labels": labels or [],
        "children": []
    }


def build_mindmap_json(parsed_data: Dict) -> Dict:
    """
    构建思维导图JSON结构

    规则：
    - 根节点：MD需求名称
    - 第二级：测试用例名称（TC开头的标题）
    - 第三级：测试步骤
    - 第四级：预期结果

    Args:
        parsed_data: 解析后的MD数据

    Returns:
        思维导图JSON结构
    """
    root_id = generate_id()
    request_info = parsed_data["request_info"]
    root_title = parsed_data["root_title"]
    cases_by_id = parsed_data["cases_by_id"]

    # 创建根节点
    root_node = create_node(
        title=root_title,
        node_id=root_id
    )

    # 添加备注信息
    notes_parts = []
    if request_info.get("request_no"):
        notes_parts.append(f"需求编号: {request_info['request_no']}")
    if request_info.get("owner"):
        notes_parts.append(f"负责人: {request_info['owner']}")
    if request_info.get("department"):
        notes_parts.append(f"涉及部门: {request_info['department']}")
    if notes_parts:
        root_node["notes"] = "\n".join(notes_parts)

    # 优先级排序
    priority_order = {"P0": 1, "P1": 2, "P2": 3}

    # 按模块分组用例
    modules = {}
    for case_id, case in cases_by_id.items():
        module = case.module if case.module else "其他"
        if module not in modules:
            modules[module] = []
        modules[module].append(case)

    # 为每个模块创建用例节点
    # 根据需求描述，测试用例标题是根节点的直接子节点
    # 按模块组织，或者直接按用例

    # 方式：按模块分组下挂用例
    for module_name in sorted(modules.keys()):
        module_cases = modules[module_name]
        sorted_cases = sorted(module_cases, key=lambda x: priority_order.get(x.priority, 99))

        for case in sorted_cases:
            # 第二级节点：测试用例名称（纯净的标题，不包含额外信息）
            # 清理标题，去掉开头多余的 - 符号
            clean_title = case.title.strip(' -').strip()
            case_node = create_node(title=clean_title)

            # 添加前置条件作为子节点（如果有）
            if case.pre_condition:
                # 前置条件不添加"前置条件："前缀，直接显示内容
                pre_node = create_node(title=case.pre_condition)
                case_node["children"].append(pre_node)
                
                # 第三级节点：测试步骤（作为前置条件的子节点）
                if case.steps:
                    # 将所有步骤合并为一个子节点，步骤之间保持换行
                    # 分解步骤 - 按数字序号分割
                    steps_lines = re.split(r'\d+\.\s*', case.steps)
                    steps_lines = [s.strip() for s in steps_lines if s.strip()]
                    
                    if len(steps_lines) >= 1:
                        # 有步骤，合并为一个节点
                        merged_steps = '\n'.join([f"{i+1}. {step}" for i, step in enumerate(steps_lines)])
                    else:
                        # 无步骤序号，直接使用原步骤内容
                        merged_steps = case.steps
                    
                    # 创建测试步骤节点
                    step_node = create_node(title=merged_steps)

                    # 第四级节点：预期结果（不添加"预期结果："前缀）
                    if case.expected_result:
                        expected_node = create_node(title=case.expected_result)
                        # 预期结果作为步骤的子节点
                        step_node["children"].append(expected_node)

                    pre_node["children"].append(step_node)
            else:
                # 无前置条件时，测试步骤作为测试用例的直接子节点
                if case.steps:
                    # 将所有步骤合并为一个子节点，步骤之间保持换行
                    # 分解步骤 - 按数字序号分割
                    steps_lines = re.split(r'\d+\.\s*', case.steps)
                    steps_lines = [s.strip() for s in steps_lines if s.strip()]
                    
                    if len(steps_lines) >= 1:
                        # 有步骤，合并为一个节点
                        merged_steps = '\n'.join([f"{i+1}. {step}" for i, step in enumerate(steps_lines)])
                    else:
                        # 无步骤序号，直接使用原步骤内容
                        merged_steps = case.steps
                    
                    # 创建测试步骤节点
                    step_node = create_node(title=merged_steps)

                    # 第四级节点：预期结果（不添加"预期结果："前缀）
                    if case.expected_result:
                        expected_node = create_node(title=case.expected_result)
                        # 预期结果作为步骤的子节点
                        step_node["children"].append(expected_node)

                    case_node["children"].append(step_node)

            # 添加用例节点到根节点
            root_node["children"].append(case_node)

    # 构建完整的JSON结构
    mindmap_json = {
        "title": root_title,
        "topic_node": root_node,
        "detached_nodes": [],
        "relations": []
    }

    return mindmap_json


def save_json(json_data: Dict, output_path: str):
    """
    保存JSON文件

    Args:
        json_data: JSON数据
        output_path: 输出文件路径
    """
    output_path_obj = Path(output_path)
    if output_path_obj.suffix != '.json':
        output_path = str(output_path_obj.with_suffix('.json'))

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)

    return output_path


def main():
    """主函数"""
    # MD文件路径
    md_file = r"C:\Users\miaoxu-jwk\测试用例_金科标品V3.6.13_保证人功能.md"

    # 检查文件是否存在
    if not Path(md_file).exists():
        print(f"错误：找不到文件 {md_file}")
        return

    print("=" * 60)
    print("MD文件解析为JSON思维导图")
    print("=" * 60)
    print(f"\n正在解析MD文件: {md_file}")

    # 解析MD文件
    parsed_data = parse_markdown_to_cases(md_file)

    print(f"需求名称: {parsed_data['root_title']}")
    print(f"需求编号: {parsed_data['request_info'].get('request_no', 'N/A')}")
    print(f"负责人: {parsed_data['request_info'].get('owner', 'N/A')}")
    print(f"解析到 {len(parsed_data['cases_by_id'])} 个测试用例")

    # 构建思维导图JSON结构
    print("\n正在构建思维导图JSON结构...")
    mindmap_json = build_mindmap_json(parsed_data)

    # 保存JSON文件
    output_file = r"C:\Users\miaoxu-jwk\测试用例脑图_JKREQUEST-5103.json"
    save_json(mindmap_json, output_file)

    print(f"\nJSON文件已生成: {output_file}")

    # 打印JSON结构概览
    print("\n" + "=" * 60)
    print("JSON结构概览:")
    print("=" * 60)
    print(f"根节点标题: {mindmap_json['title']}")
    print(f"根节点ID: {mindmap_json['topic_node']['id']}")
    print(f"根节点子节点数量: {len(mindmap_json['topic_node']['children'])}")

    # 统计各层级节点数量
    total_steps = 0
    total_expected = 0
    for case_node in mindmap_json['topic_node']['children']:
        for child in case_node['children']:
            if not child['title'].startswith('前置条件'):
                total_steps += 1
                total_expected += len(child['children'])

    print(f"测试步骤节点数量: {total_steps}")
    print(f"预期结果节点数量: {total_expected}")


if __name__ == "__main__":
    main()
