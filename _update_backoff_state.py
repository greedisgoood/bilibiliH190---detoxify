def _update_backoff_state(self, reason_type, success):
    """
    更新智能退避状态
    
    Args:
        reason_type: 举报理由类型
        success: 是否成功
    """
    # 更新举报成功率统计
    if reason_type in self.report_success_stats:
        self.report_success_stats[reason_type]["attempts"] += 1
        if success:
            self.report_success_stats[reason_type]["success"] += 1
    
    # 更新退避状态
    if success:
        # 成功后重置连续失败计数
        self.backoff_state["consecutive_failures"] = 0
        self.backoff_state["current_backoff_time"] = self.report_delay["backoff"]["initial"]
        self.backoff_state["last_success_time"] = time.time()
        
        # 重置该理由的失败计数
        if reason_type in self.backoff_state["reason_failures"]:
            self.backoff_state["reason_failures"][reason_type] = 0
    else:
        # 失败后增加连续失败计数
        self.backoff_state["consecutive_failures"] += 1
        
        # 增加该理由的失败计数
        if reason_type not in self.backoff_state["reason_failures"]:
            self.backoff_state["reason_failures"][reason_type] = 0
        self.backoff_state["reason_failures"][reason_type] += 1
        
        # 如果连续失败次数超过阈值，增加退避时间
        if self.backoff_state["consecutive_failures"] >= 3:
            # 增加退避时间，但不超过最大值
            new_backoff_time = min(
                self.backoff_state["current_backoff_time"] * self.report_delay["backoff"]["factor"],
                self.report_delay["backoff"]["max"]
            )
            self.backoff_state["current_backoff_time"] = new_backoff_time
            print(f"连续失败{self.backoff_state['consecutive_failures']}次，增加退避时间至{new_backoff_time:.1f}秒")
            
            # 如果某个理由失败次数过多，将其加入黑名单
            for r_type, failures in self.backoff_state["reason_failures"].items():
                if failures >= 5:  # 连续5次失败
                    print(f"举报理由 {r_type} 连续失败{failures}次，暂时避免使用")
    
    # 检查是否需要重置退避状态
    current_time = time.time()
    if current_time - self.backoff_state["last_success_time"] > self.report_delay["backoff"]["reset_after"]:
        # 长时间没有成功，重置退避状态
        self.backoff_state["consecutive_failures"] = 0
        self.backoff_state["current_backoff_time"] = self.report_delay["backoff"]["initial"]
        self.backoff_state["reason_failures"] = {}
        print(f"长时间未成功举报，重置退避状态")
