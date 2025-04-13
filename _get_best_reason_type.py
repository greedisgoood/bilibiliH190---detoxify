def _get_best_reason_type(self, candidates):
    """
    根据历史成功率选择最佳举报理由
    
    Args:
        candidates: 候选举报理由列表
        
    Returns:
        best_reason: 最佳举报理由
    """
    if not candidates:
        return 7  # 默认使用引战
    
    best_reason = None
    best_rate = -1
    
    for reason in candidates:
        stats = self.report_success_stats.get(reason, {"attempts": 0, "success": 0})
        if stats["attempts"] > 5:  # 有足够样本
            success_rate = stats["success"] / stats["attempts"]
            if success_rate > best_rate:
                best_rate = success_rate
                best_reason = reason
    
    # 如果没有足够的统计数据，使用预设优先级
    if best_reason is None:
        # 优先级: 引战(7) > 人身攻击(4) > 政治敏感(9) > 违法违禁(1)
        priority_order = [7, 4, 9, 1]
        for reason in priority_order:
            if reason in candidates:
                return reason
    
    return best_reason or candidates[0]  # 默认返回第一个候选
