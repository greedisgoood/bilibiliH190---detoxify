def _ensure_log_dirs(self):
    """确保日志目录存在"""
    import os
    
    # 确保logs目录存在
    if not os.path.exists("logs"):
        os.makedirs("logs")
    
    # 确保误判样本目录存在
    false_positives_dir = os.path.dirname(self.false_positives_file)
    if not os.path.exists(false_positives_dir):
        os.makedirs(false_positives_dir)
    
    false_negatives_dir = os.path.dirname(self.false_negatives_file)
    if not os.path.exists(false_negatives_dir):
        os.makedirs(false_negatives_dir)
