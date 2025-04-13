def analyze_comment_context(self, comment, video_title, other_comments=None):
    """
    分析评论的上下文，考虑视频标题和其他评论
    
    Args:
        comment: 评论内容
        video_title: 视频标题
        other_comments: 同一视频下的其他评论
        
    Returns:
        context_score: 上下文相关性得分
        context_info: 上下文分析信息
    """
    if not comment or not video_title:
        return 0, {}
    
    context_score = 0
    context_info = {}
    
    # 1. 检查评论与视频标题的相关性
    # 如果视频标题包含华为相关关键词，增加权重
    huawei_related = False
    xiaomi_related = False
    
    # 检查视频标题是否与华为相关
    if any(kw in video_title.lower() for kw in self.fanatic_detector.huawei_special_terms):
        huawei_related = True
        context_score += 0.5
        context_info["video_huawei_related"] = True
    
    # 检查视频标题是否与小米相关
    if any(kw in video_title.lower() for kw in self.fanatic_detector.xiaomi_special_terms):
        xiaomi_related = True
        context_score += 0.5
        context_info["video_xiaomi_related"] = True
    
    # 2. 检查是否是回复其他评论
    is_reply = False
    if isinstance(comment, dict) and comment.get("parent", 0) > 0:
        is_reply = True
        context_score += 0.3
        context_info["is_reply"] = True
    
    # 3. 分析评论内容与视频主题的相关性
    content = ""
    if isinstance(comment, dict) and "content" in comment:
        if isinstance(comment["content"], dict) and "message" in comment["content"]:
            content = comment["content"]["message"]
        elif isinstance(comment["content"], str):
            content = comment["content"]
    elif isinstance(comment, str):
        content = comment
    
    # 如果评论内容与视频主题相关，增加权重
    if huawei_related and any(kw in content.lower() for kw in self.fanatic_detector.huawei_special_terms):
        context_score += 0.4
        context_info["comment_huawei_related"] = True
    
    if xiaomi_related and any(kw in content.lower() for kw in self.fanatic_detector.xiaomi_special_terms):
        context_score += 0.4
        context_info["comment_xiaomi_related"] = True
    
    # 4. 分析评论情感与视频主题的一致性
    # 如果视频是关于华为的，而评论对华为持负面态度，可能是竞品粉丝
    # 如果视频是关于小米的，而评论对小米持负面态度，可能是华为极端粉丝
    if huawei_related:
        sentiment_score = self.fanatic_detector._analyze_emotional_intensity(content)
        if sentiment_score > 3:  # 情感强度较高
            context_score += 0.3
            context_info["high_emotion_huawei_video"] = True
    
    if xiaomi_related:
        sentiment_score = self.fanatic_detector._analyze_emotional_intensity(content)
        if sentiment_score > 3:  # 情感强度较高
            context_score += 0.3
            context_info["high_emotion_xiaomi_video"] = True
    
    # 5. 分析其他评论的情况（如果提供）
    if other_comments and len(other_comments) > 0:
        # 计算同一视频下极端评论的比例
        extreme_count = 0
        for other_comment in other_comments[:20]:  # 只分析前20条评论
            other_content = ""
            if isinstance(other_comment, dict):
                if isinstance(other_comment.get("content"), dict):
                    other_content = other_comment["content"].get("message", "")
                elif isinstance(other_comment.get("content"), str):
                    other_content = other_comment["content"]
            
            if other_content:
                # 简单检查是否可能是极端评论
                is_extreme, _ = self.fanatic_detector.enhanced_extreme_fan_detection(other_content)
                if is_extreme:
                    extreme_count += 1
        
        # 如果同一视频下极端评论比例较高，增加权重
        extreme_ratio = extreme_count / min(len(other_comments), 20)
        if extreme_ratio > 0.3:  # 超过30%的评论是极端评论
            context_score += 0.4
            context_info["high_extreme_ratio"] = extreme_ratio
    
    return context_score, context_info
