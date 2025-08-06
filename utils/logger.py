import os
import logging
import logging.handlers

def setup_loggers():
    """配置并返回根日志记录器和操作日志记录器。"""
    # 配置根日志记录器
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    
    # 配置操作日志记录器
    op_log_dir = 'logs'
    os.makedirs(op_log_dir, exist_ok=True)
    op_log_file = os.path.join(op_log_dir, 'operations.log')
    
    op_logger = logging.getLogger('operations')
    op_logger.setLevel(logging.INFO)
    
    # 防止在重新加载时重复添加处理器
    if not op_logger.handlers:
        handler = logging.handlers.RotatingFileHandler(
            op_log_file, maxBytes=5*1024*1024, backupCount=2, encoding='utf-8'
        )
        formatter = logging.Formatter('%(asctime)s - %(message)s')
        handler.setFormatter(formatter)
        op_logger.addHandler(handler)
        
    return logging.getLogger(), op_logger

# 在模块级别调用一次，以便其他模块可以导入 logger 和 op_logger
logger, op_logger = setup_loggers()
