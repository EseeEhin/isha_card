import json
from .logger import logger

def load_json_data(file_path, default_data=None):
    """从指定路径加载 JSON 数据。"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning(f"无法加载 {file_path}: {e}。将返回默认数据。")
        return default_data if default_data is not None else []

def save_json_data(file_path, data):
    """将数据保存到指定的 JSON 文件。"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"数据已成功保存到 {file_path}")
    except Exception as e:
        logger.error(f"保存数据到 {file_path} 时出错: {e}")
