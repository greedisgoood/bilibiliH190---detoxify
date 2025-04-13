def auto_report_malicious_comments(self, video_identifier, max_comments=100, max_reports=10):
    """
    自动检测并举报视频下的恶意评论 (增强版)
    
    Args:
        video_identifier (str): 视频ID或URL
        max_comments (int): 最多处理的评论数量
        max_reports (int): 最多举报的评论数量
        
    Returns:
        dict: 处理结果统计
    """
    # 初始化统计信息
    stats = {
        "video_id": video_identifier,
        "video_title": "",
        "total_comments": 0,
        "processed_comments": 0,
        "malicious_comments": 0,
        "reported_comments": 0,
        "report_failed": 0,
        "report_reason_stats": {},
        "malicious_details": []
    }
    
    # 解析视频ID
    oid = self._extract_video_id(video_identifier)
    if not oid:
        print(f"无法解析视频ID: {video_identifier}")
        return stats
    
    # 获取视频信息
    video_info = self.get_video_info(oid)
    title = video_info.get("title", "未知标题")
    stats["video_title"] = title
    print(f"\n处理视频: {title} (ID: {oid})")
    
    # 获取评论
    all_comments_for_video = []
    try:
        all_comments = self.get_all_comments(oid, max_count=max_comments)
        all_comments_for_video = all_comments
        stats["total_comments"] = len(all_comments)
        print(f"获取到 {len(all_comments)} 条评论")
    except Exception as e:
        print(f"获取评论失败: {e}")
        return stats
    
    # 记录已举报的评论ID，避免重复举报
    reported_rpids_in_video = set()
    
    # 第一阶段：检测恶意评论
    detected_malicious_comments = []
    
    for comment in all_comments:
        stats["processed_comments"] += 1
        
        # 提取评论信息
        rpid = comment.get("rpid", 0)
        mid = comment.get("mid", 0)
        uname = comment.get("member", {}).get("uname", "未知用户")
        like_count = comment.get("like", 0)
        parent = comment.get("parent", 0)
        root = comment.get("root", 0)
        
        # 提取评论内容
        content = ""
        if isinstance(comment.get("content"), dict) and "message" in comment["content"]:
            content = comment["content"]["message"]
        elif isinstance(comment.get("content"), str):
            content = comment["content"]
        
        if not content or rpid in reported_rpids_in_video:
            continue
            
        try:
            # === 调用模型进行检测 ===
            detection_result = self.fanatic_detector.detect_huawei_fanatic(content, rpid, mid)
            is_extreme = detection_result.get("is_huawei_fanatic", False)
            confidence = detection_result.get("confidence", 0.0)
            detection_summary = detection_result.get("detection_summary", {})
            
            # 如果启用了上下文分析，考虑视频标题和其他评论
            if self.context_analysis_enabled and is_extreme:
                context_score, context_info = self.analyze_comment_context(comment, title, all_comments_for_video)
                # 如果上下文得分较高，增加置信度
                if context_score > 0.5:
                    confidence = min(confidence + context_score * 0.2, 1.0)  # 最多增加20%置信度
                    print(f"  上下文分析: 得分={context_score:.2f}, 置信度提升至{confidence:.2f}")
                    # 将上下文信息添加到检测摘要中
                    detection_summary["context_info"] = context_info
            
            # 将检测到的恶意评论添加到列表中，用于后续排序
            if is_extreme:
                stats["malicious_comments"] += 1
                
                # 提取极端类型和推理过程
                extreme_types = detection_summary.get("extreme_types", [])
                reasoning = detection_summary.get("reasoning", [])
                
                # 记录详细信息
                stats["malicious_details"].append({
                    "video_id": video_identifier,
                    "video_title": title,
                    "comment_rpid": rpid,
                    "comment_content": content,
                    "user_name": uname,
                    "confidence": confidence,
                    "extreme_types": extreme_types,
                    "reasoning": reasoning
                })
                
                # 将评论添加到待举报列表
                detected_malicious_comments.append({
                    "rpid": rpid,
                    "mid": mid,
                    "uname": uname,
                    "content": content,
                    "confidence": confidence,
                    "detection_summary": detection_summary,
                    "like_count": like_count,
                    "parent": parent,
                    "root": root,
                    "comment_obj": comment  # 保存原始评论对象，用于计算优先级
                })
                
                print(f"\n检测到恶意评论 (rpid={rpid}, 用户={uname}, 置信度={confidence:.2f})")
                print(f"  内容: {content[:100]}...")
                if extreme_types:
                    print(f"  极端类型: {', '.join(extreme_types)}")
                
        except Exception as e:
            print(f"处理评论时出错: {e}")
            continue
    
    # 第二阶段：按优先级排序恶意评论并举报
    if detected_malicious_comments:
        print(f"\n--- 第二阶段: 按优先级排序并举报 ({len(detected_malicious_comments)} 条恶意评论) ---")
        
        # 计算每条评论的优先级分数
        for comment in detected_malicious_comments:
            priority_score = self.calculate_report_priority(comment["comment_obj"], {
                "confidence": comment["confidence"],
                "detection_summary": comment["detection_summary"]
            })
            comment["priority_score"] = priority_score
        
        # 按优先级分数排序
        detected_malicious_comments.sort(key=lambda x: x["priority_score"], reverse=True)
        
        # 限制每个视频的举报数量
        max_reports_per_video = min(len(detected_malicious_comments), max_reports)
        
        for i, comment in enumerate(detected_malicious_comments[:max_reports_per_video]):
            rpid = comment["rpid"]
            content = comment["content"]
            confidence = comment["confidence"]
            detection_summary = comment["detection_summary"]
            priority_score = comment["priority_score"]
            
            # 如果已经举报过，跳过
            if rpid in reported_rpids_in_video:
                continue
                
            print(f"\n处理排序后的恶意评论 {i+1}/{max_reports_per_video} (rpid={rpid}, 优先级={priority_score:.2f}, 置信度={confidence:.2f})")
            print(f"  内容: {content[:100]}...")
            
            # 确定举报原因和详情
            report_reason_type = self._determine_report_reason_type(content, detection_summary)
            report_detail = self._generate_report_detail(content, report_reason_type, detection_summary)
            
            # 统计举报原因
            reason_name = self.get_report_reason_name(report_reason_type)
            stats["report_reason_stats"][reason_name] = stats["report_reason_stats"].get(reason_name, 0) + 1
            
            # 执行举报
            if not isinstance(oid, str): oid = str(oid)
            report_api_result = self.report_comment(oid, rpid, report_reason_type, report_detail)
            
            if report_api_result and report_api_result.get("code") == 0:
                stats["reported_comments"] += 1
                reported_rpids_in_video.add(rpid)
                print(f"成功举报评论 rpid={rpid}")
            else:
                stats["report_failed"] += 1
                print(f"举报失败: {report_api_result}")
                
            # 每次举报后添加随机延迟
            if i < max_reports_per_video - 1:
                delay = random.uniform(5, 10)
                print(f"等待 {delay:.1f} 秒后继续...")
                time.sleep(delay)
    
    # 视频之间添加延时
    time.sleep(random.uniform(3, 5))
    
    return stats
