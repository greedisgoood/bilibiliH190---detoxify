# bilibili_comment_detector.py
# B站恶意评论自动检测与举报工具

import requests
import json
import time
import random
import re
import os
from datetime import datetime
from dotenv import load_dotenv
from tqdm import tqdm
from model import HuaweiFanaticDetector
import logging

# 设置基本日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"logs/bilibili_comment_detector_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("BilibiliCommentDetector")

class BilibiliCommentDetector:
    def __init__(self):
        """初始化B站评论检测器"""
        # 基础设置
        self.session = requests.Session()
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

        # 加载环境变量
        load_dotenv()

        # 设置cookies
        self._load_cookies()

        # 初始化 csrf_token
        self.csrf_token = None
        self.cookies_str = None

        # 从cookies中获取csrf_token
        self._get_csrf_token()

        # 恶意评论检测设置 (已移至 model.py)
        # self.malicious_threshold = 5

        # 会话信息
        self.mid = None
        self.uname = None

        # 获取登录信息
        self._get_login_info()

        # 初始化华为极端粉丝检测器
        self.fanatic_detector = HuaweiFanaticDetector()

        # 设置BERT模型路径 (已不再需要，model.py 不使用BERT)
        # self.model_path = os.path.join(os.path.dirname(__file__), "model", "bert-base-chinese")
        # if not os.path.exists(self.model_path):
        #     print(f"警告：本地BERT模型路径不存在: {self.model_path}")
        #     print("请确保模型文件已正确放置在 model/bert-base-chinese 目录下")
        # else:
        #     print(f"已找到本地BERT模型: {self.model_path}")

        # 举报延时配置
        self.report_delay = {
            "min": 15,  # 最小延时（秒）
            "max": 60,  # 最大延时（秒）
            "random": True,  # 是否使用随机延迟
            "backoff": {  # 智能退避机制
                "initial": 30,  # 初始退避时间（秒）
                "factor": 1.5,  # 退避因子
                "max": 300,  # 最大退避时间（秒）
                "reset_after": 1800  # 重置退避时间的间隔（秒）
            }
        }

        # 举报频率限制
        self.report_limit = {
            "hourly": 30,  # 每小时最大举报次数
            "daily": 80,  # 每天最大举报次数
            "cooldown": 30,  # 连续举报冷却时间（秒）
            "success_interval": 30  # 成功举报后的最小间隔（秒）
        }

        # 智能退避机制状态
        self.backoff_state = {
            "consecutive_failures": 0,  # 连续失败次数
            "current_backoff_time": self.report_delay["backoff"]["initial"],  # 当前退避时间
            "last_success_time": time.time(),  # 上次成功时间
            "reason_failures": {}  # 各举报理由的失败次数
        }

        # 举报成功率统计
        self.report_success_stats = {
            1: {"attempts": 0, "success": 0},  # 违法违禁
            2: {"attempts": 0, "success": 0},  # 色情低俗
            3: {"attempts": 0, "success": 0},  # 赌博诈骗
            4: {"attempts": 0, "success": 0},  # 人身攻击
            5: {"attempts": 0, "success": 0},  # 侵犯隐私
            6: {"attempts": 0, "success": 0},  # 垃圾广告
            7: {"attempts": 0, "success": 0},  # 引战
            8: {"attempts": 0, "success": 0},  # 剧透
            9: {"attempts": 0, "success": 0},  # 政治敏感
            13: {"attempts": 0, "success": 0}  # 青少年不良信息
        }

        # 误判样本收集
        self.false_positives_file = "logs/false_positives.jsonl"
        self.false_negatives_file = "logs/false_negatives.jsonl"
        self._ensure_log_dirs()

        # 上下文分析配置
        self.context_analysis_enabled = True

        print("B站恶意评论检测器已初始化") # 使用 print

    def _ensure_log_dirs(self):
        """确保日志目录存在"""
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



    def record_false_negative(self, content, comment_info=None):
        """记录漏判样本"""
        try:
            with open(self.false_negatives_file, "a", encoding="utf-8") as f:
                record = {
                    "content": content,
                    "comment_info": comment_info or {},
                    "timestamp": datetime.now().isoformat()
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

            print(f"已记录漏判样本到 {self.false_negatives_file}")
            return True
        except Exception as e:
            print(f"记录漏判样本失败: {e}")
            return False





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

    def _ensure_log_dirs(self):
        """确保日志目录存在"""
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

    def _load_cookies(self):
        """加载cookies"""
        cookie_string = os.getenv("BILIBILI_COOKIE")
        if not cookie_string:
            print("警告: 未设置BILIBILI_COOKIE环境变量")
            return False

        cookies_dict = self._parse_cookie_string(cookie_string)
        self._set_cookies(cookies_dict)

        # 获取csrf_token
        self._get_csrf_token()

        return True

    def _parse_cookie_string(self, cookie_str):
        """解析cookie字符串"""
        cookies_dict = {}
        for item in cookie_str.split(';'):
            if '=' in item:
                key, value = item.strip().split('=', 1)
                cookies_dict[key] = value
        return cookies_dict

    def _set_cookies(self, cookies_dict):
        """设置cookies到会话"""
        for key, value in cookies_dict.items():
            self.session.cookies.set(key, value)

    def _get_csrf_token(self):
        """从cookies中获取csrf_token"""
        try:
            # 先从cookie获取
            if "bili_jct" in self.session.cookies:
                self.csrf_token = self.session.cookies.get("bili_jct")
                print(f"从cookie获取到csrf_token: {self.csrf_token[:3]}***{self.csrf_token[-3:]}")
                return True

            # 如果cookie中没有，尝试请求一个页面获取
            url = "https://www.bilibili.com"
            headers = {"User-Agent": self.user_agent}

            response = self.session.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                # 尝试从新cookie中获取
                if "bili_jct" in self.session.cookies:
                    self.csrf_token = self.session.cookies.get("bili_jct")
                    print(f"请求页面后获取到csrf_token: {self.csrf_token[:3]}***{self.csrf_token[-3:]}")
                    return True

            print("无法获取csrf_token，可能未登录")
            return False
        except Exception as e:
            print(f"获取csrf_token出错: {str(e)}")
            return False

    def _get_login_info(self):
        """获取登录用户信息"""
        try:
            url = "https://api.bilibili.com/x/web-interface/nav"
            headers = {"User-Agent": self.user_agent}

            response = self.session.get(url, headers=headers)
            data = response.json()

            if data["code"] == 0 and data["data"]["isLogin"]:
                self.mid = data["data"]["mid"]
                self.uname = data["data"]["uname"]
                print(f"已登录账号: {self.uname} (UID: {self.mid})")
                return True
            else:
                print("未登录或登录已过期")
                return False
        except Exception as e:
            print(f"获取登录信息失败: {e}")
            return False

    def check_login_status(self):
        """检查登录状态"""
        if not self.mid:
            return self._get_login_info()
        return True

    def search_videos(self, keyword, page=1, order='totalrank', video_type=0):
        """
        搜索B站视频

        Args:
            keyword: 搜索关键词
            page: 页码
            order: 排序方式 (totalrank:综合排序, pubdate:最新发布, click:最多点击, dm:最多弹幕, stow:最多收藏)
            video_type: 视频类型 (0:全部, 1:视频, 2:番剧, 3:影视, 4:直播)

        Returns:
            视频列表
        """
        print(f"\n正在搜索关键词 '{keyword}' 的视频 (第 {page} 页)...")

        try:
            url = "https://api.bilibili.com/x/web-interface/search/type"
            params = {
                "keyword": keyword,
                "page": page,
                "order": order,
                "search_type": "video",
                "tids": video_type,
                "platform": "web"
            }

            headers = {
                "User-Agent": self.user_agent,
                "Referer": "https://search.bilibili.com/",
                "Origin": "https://search.bilibili.com"
            }

            response = self.session.get(url, params=params, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()

                if data["code"] == 0 and "data" in data and "result" in data["data"]:
                    videos = data["data"]["result"]
                    print(f"找到 {len(videos)} 个视频")

                    # 处理视频信息
                    processed_videos = []
                    for video in videos:
                        try:
                            # 尝试多种方式提取AID
                            aid = None

                            # 方法1: 从arcurl中提取aid
                            arcurl = video.get("arcurl", "")
                            aid_match = re.search(r'aid=(\d+)', arcurl)
                            if aid_match:
                                aid = aid_match.group(1)

                            # 方法2: 直接从aid字段获取
                            if not aid and "aid" in video:
                                aid = str(video["aid"])

                            # 方法3: 从avid字段获取
                            if not aid and "avid" in video:
                                aid = str(video["avid"])

                            # 方法4: 从AV号提取
                            if not aid and "av_id" in video:
                                aid = str(video["av_id"])

                            # 方法5: 从ID字段提取
                            if not aid and "id" in video:
                                aid = str(video["id"])

                            # 从bvid中提取bvid
                            bvid = video.get("bvid", "")

                            # 如果没有aid但有bvid，尝试转换
                            if not aid and bvid:
                                try:
                                    # 尝试从网页获取av号
                                    print(f"尝试从BV号获取AV号: {bvid}")
                                    bv_url = f"https://www.bilibili.com/video/{bvid}"
                                    headers = {
                                        "User-Agent": self.user_agent,
                                        "Referer": "https://www.bilibili.com"
                                    }
                                    response = self.session.get(bv_url, headers=headers, timeout=10)
                                    if response.status_code == 200:
                                        av_match = re.search(r'"aid":(\d+)', response.text)
                                        if av_match:
                                            aid = av_match.group(1)
                                            print(f"成功从BV号获取AV号: {aid}")
                                except Exception as e:
                                    print(f"转换BV号到AV号时出错: {e}")

                            if not aid and not bvid:
                                print(f"无法从视频信息提取ID: {video}")
                                continue

                            processed_video = {
                                "aid": aid,
                                "bvid": bvid,
                                "title": video.get("title", "").replace("<em class=\"keyword\">", "").replace("</em>", ""),
                                "author": video.get("author", ""),
                                "mid": video.get("mid", 0),
                                "duration": video.get("duration", ""),
                                "play": video.get("play", 0),
                                "danmaku": video.get("video_review", 0),
                                "favorites": video.get("favorites", 0),
                                "comments": video.get("review", 0),
                                "url": f"https://www.bilibili.com/video/{bvid if bvid else 'av'+aid}"
                            }
                            processed_videos.append(processed_video)
                        except Exception as e:
                            print(f"处理视频信息出错: {e}")
                            continue

                    return processed_videos
                else:
                    print(f"搜索API返回错误: {data.get('message', '未知错误')}")
            else:
                print(f"搜索请求失败，状态码: {response.status_code}")

        except Exception as e:
            print(f"搜索视频出错: {e}")

        return []

    def get_video_comments(self, aid_or_bvid, page=1):
        """
        获取视频评论，支持多种API尝试和BV号转换

        Args:
            aid_or_bvid: 视频ID (av号或BV号)
            page: 页码

        Returns:
            评论列表
        """
        aid = None
        # 检查是否为BV号，如果是则尝试转换
        if isinstance(aid_or_bvid, str) and aid_or_bvid.startswith("BV"):
            print(f"检测到BV号: {aid_or_bvid}，尝试转换为av号...")
            try:
                # 直接从网页获取av号
                bv_url = f"https://www.bilibili.com/video/{aid_or_bvid}"
                headers = {
                    "User-Agent": self.user_agent, # 使用类属性
                    "Referer": "https://www.bilibili.com"
                }
                response = self.session.get(bv_url, headers=headers, timeout=10)
                if response.status_code == 200:
                    match = re.search(r'"aid":(\d+)', response.text)
                    if match:
                        aid = match.group(1)
                        print(f"成功将BV号 {aid_or_bvid} 转换为av号: {aid}")
                    else:
                        print(f"无法从网页提取av号: {aid_or_bvid}")
                        return [] # 如果无法转换，则返回空列表
                else:
                    print(f"请求BV号页面失败，状态码: {response.status_code}")
                    return []
            except Exception as e:
                print(f"BV号转换出错: {e}")
                return []
        elif isinstance(aid_or_bvid, str) and aid_or_bvid.isdigit():
            aid = aid_or_bvid
        elif isinstance(aid_or_bvid, int):
             aid = str(aid_or_bvid)
        else:
            print(f"无效的视频ID格式: {aid_or_bvid}")
            return []

        if not aid:
             print("无法获取有效的av号")
             return []

        # 首先使用备用API（已证明更有效）
        backup_url = "https://api.bilibili.com/x/v2/reply/main"
        params = {
            "type": 1,
            "oid": aid,
            "mode": 3,  # 按热度排序
            "next": page, # 使用 next 参数进行分页
            "ps": 30
        }

        headers = {
            "User-Agent": self.user_agent,
            "Referer": f"https://www.bilibili.com/video/av{aid}"
        }

        try:
            print(f"\n正在获取视频 av{aid} 的评论 (next={page})...") # page 现在代表 next 参数
            print(f"使用API: {backup_url}")
            # print(f"请求参数: {params}") # 避免打印过多

            # 添加随机延迟，避免频繁请求
            time.sleep(random.uniform(1, 2))

            response = self.session.get(backup_url, params=params, headers=headers, timeout=15)
            # print(f"API响应状态码: {response.status_code}") # 减少冗余打印

            if response.status_code == 200:
                data = response.json()
                # print(f"API返回码: {data.get('code')}") # 减少冗余打印

                if data["code"] == 0:
                    if "data" in data and data["data"].get("replies"): # 检查 replies 是否存在且不为 None
                        replies = data["data"]["replies"]
                        print(f"成功获取到 {len(replies)} 条评论")
                        # 注意：此 API 可能返回空列表表示没有更多评论，而不是错误
                        # 需要检查是否有 cursor.is_end 字段来判断是否结束
                        # is_end = data.get("data", {}).get("cursor", {}).get("is_end", False)
                        # if not replies and is_end:
                        #    print("已到达评论末页 (根据 cursor)")
                        return replies
                    else:
                        # data["replies"] 可能为 None 或空列表，这不一定是错误
                        print("评论列表为空或数据结构异常")
                        return [] # 返回空列表表示没有评论或已结束
                else:
                    print(f"API返回错误: {data.get('message', '未知错误')}")
            else:
                print(f"API请求失败，状态码: {response.status_code}")
        except Exception as e:
            print(f"API请求失败: {e}")

        print("获取评论失败")
        return []

    def get_video_oid(self, video_id):
        """
        从视频ID获取OID（举报用）

        Args:
            video_id: 视频ID，可以是BV号或av号

        Returns:
            oid: 用于评论举报的OID
        """
        try:
            # 如果已经是纯数字，可能是aid
            if isinstance(video_id, str) and video_id.isdigit():
                return video_id
            if isinstance(video_id, int):
                return str(video_id)

            # 如果是av开头，提取数字
            if isinstance(video_id, str) and video_id.lower().startswith("av"):
                aid = video_id[2:].strip()
                if aid.isdigit():
                    return aid

            # 如果是BV号，需要请求页面获取aid
            if isinstance(video_id, str) and video_id.startswith("BV"):
                print(f"从BV号获取AID: {video_id}")
                url = f"https://www.bilibili.com/video/{video_id}"
                headers = {
                    "User-Agent": self.user_agent,
                    "Referer": "https://www.bilibili.com"
                }

                response = self.session.get(url, headers=headers, timeout=10)

                if response.status_code == 200:
                    # 尝试从HTML中提取aid
                    aid_pattern = r'"aid":(\d+)'
                    aid_match = re.search(aid_pattern, response.text)

                    if aid_match:
                        aid = aid_match.group(1)
                        print(f"成功获取AID: {aid}")
                        return aid

                    # 如果没有找到，尝试其他模式
                    aid_pattern2 = r'window\\.__INITIAL_STATE__=.*?"aid":(\d+)'
                    aid_match2 = re.search(aid_pattern2, response.text)

                    if aid_match2:
                        aid = aid_match2.group(1)
                        print(f"成功获取AID（方法2）: {aid}")
                        return aid

                    print("从网页中无法提取AID")
                else:
                    print(f"获取视频页面失败: HTTP {response.status_code}")

            print(f"无法从ID获取OID: {video_id}")
            return None

        except Exception as e:
            print(f"获取视频OID出错: {str(e)}")
            return None

    def analyze_comment_features(self, content):
        """
        分析评论特征

        Args:
            content: 评论内容

        Returns:
            dict: 特征字典
        """
        if not content:
            return {}

        # 初始化特征字典
        features = {
            "length": len(content),
            "has_url": bool(re.search(r'https?://\S+|www\.\S+', content)),
            "has_contact": self._contains_contact_info(content),
            "has_repeated_chars": self._has_repeated_chars(content),
            "has_repeated_puncts": self._has_repeated_punctuation(content),
            "has_emoji": self._contains_emoji(content),
            "has_mention": "@" in content,
            "keywords": [],
            "patterns": []
        }

        # 检查关键词
        keyword_categories = {
            "brand_attack": ["米猴", "米蛆", "果蛆", "三蛆", "越南厂", "高通垃圾", "联发科垃圾", "苹果垃圾", "小米垃圾", "三星垃圾"],
            "discrimination": ["洋垃圾", "美帝", "美狗", "日本狗", "韩国狗", "台巴子", "台毒", "港毒"],
            "personal_attack": ["脑残", "智障", "傻逼", "废物", "狗东西", "滚蛋", "去死", "有病", "神经病", "白痴", "蠢货", "猪脑子"],
            "extreme_emotion": ["最好", "最强", "第一", "无敌", "碾压", "吊打", "秒杀", "完爆", "暴打", "遥遥领先"],
            "extreme_expression": ["天下第一", "宇宙第一", "永远的神", "一生推", "唯一选择", "永远支持", "永远的神", "没有之一"],
            "nationalism": ["爱国", "卖国", "崇洋媚外", "汉奸", "民族脊梁", "民族的骄傲", "国家的骄傲", "中国的骄傲", "中国的希望"],
            "conspiracy": ["打压", "封锁", "制裁", "勾结", "出卖", "背叛", "卖国", "里应外合", "潜伏", "渗透"]
        }

        # 检查每个类别的关键词
        for category, words in keyword_categories.items():
            for word in words:
                if word in content:
                    features["keywords"].append((word, category))

        # 检查极端表达模式
        extreme_patterns = [
            (r"(华为|中国|国产).*?好.*?(苹果|三星|小米|谷歌|安卓|外国).*?不行", "极端对立"),
            (r"支持(华为|国产).*?抵制(苹果|三星|小米|谷歌|安卓|外国)", "极端对立"),
            (r"用(苹果|三星|小米|谷歌|安卓).*?就是.*?(卖国|崇洋媚外|汉奸)", "极端对立"),
            (r"华为.*?领先.*?(\d+年|全球|世界|美国|苹果|三星)", "极端夸大"),
            (r"华为.*?(吊打|碾压|秒杀).*?(苹果|三星|小米|谷歌)", "极端夸大"),
            (r"华为.*?(民族脊梁|民族之光|国产之光|中国之光)", "极端民族主义"),
            (r"支持华为.*?就是支持.*?中国", "极端民族主义"),
            (r"不用华为.*?就是.*?(卖国|汉奸)", "极端民族主义"),
            (r"喷华为的.*?都是.*?(美国|西方).*?(走狗|特务)", "极端阴谋论"),
            (r"(美国|西方).*?不想看到.*?华为.*?强大", "极端阴谋论"),
            (r"小米.*?(窃取|偷窥|监控).*?用户.*?数据", "极端阴谋论"),
            (r"用(苹果|小米|三星)的.*?智商.*?(欠费|下线|充值)", "人身攻击"),
            (r"(苹果|小米|三星)粉丝.*?脑子.*?(进水|有问题)", "人身攻击"),
            (r"雷军.*?(傻|蠢|垃圾|无能|骗子)", "人身攻击")
        ]

        # 检查每个极端模式
        for pattern, label in extreme_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                features["patterns"].append((pattern, label))

        return features

    def _contains_contact_info(self, content):
        """检查是否包含联系方式"""
        if not content:
            return False

        # 微信/QQ号码模式
        patterns = [
            r'[微信|加微|扣扣|企鹅|加我|联系我|私聊]+[^\w]*([\d]{5,12})',
            r'v[信|x][：|:]([a-zA-Z\d_-]{5,20})',
            r'VX[:|：]([a-zA-Z\d_-]{5,20})',
            r'[扣|Ｑ|Qq|ＱＱ|qq|QQ]+\s*[:：]?\s*([\d]{5,12})',
            r'电话[:|：]?([\d]{11})',
            r'手机[:|：]?([\d]{11})'
        ]

        for pattern in patterns:
            if re.search(pattern, content):
                return True

        return False

    def _has_repeated_chars(self, content):
        """检查是否包含重复字符"""
        if not content:
            return False

        # 检查连续重复的相同字符（如：哈哈哈哈哈哈）
        for char in set(content):
            # 排除常见标点和空格
            if char.isalnum() and char * 5 in content:  # 至少连续出现5次非标点字符
                return True

        return False

    def _has_repeated_punctuation(self, content):
        """检查是否包含重复标点"""
        if not content:
            return False

        # 检查重复的标点符号
        punctuation = ',.!?;:。，、！？；：'

        for punct in punctuation:
            if punct * 4 in content:  # 至少连续出现4次
                return True

        return False

    def _contains_emoji(self, content):
        """检查是否包含表情符号"""
        emoji_pattern = re.compile("["
            u"\U0001F600-\U0001F64F"  # emoticons
            u"\U0001F300-\U0001F5FF"  # symbols & pictographs
            u"\U0001F680-\U0001F6FF"  # transport & map symbols
            u"\U0001F700-\U0001F77F"  # alchemical symbols
            u"\U0001F780-\U0001F7FF"  # Geometric Shapes
            u"\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
            u"\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
            u"\U0001FA00-\U0001FA6F"  # Chess Symbols
            u"\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
            u"\U00002702-\U000027B0"  # Dingbats
            u"\U000024C2-\U0001F251"
            "]+", flags=re.UNICODE)

        # 检查 B站特定表情格式，如 [doge]
        bilibili_emoji_pattern = r'\\[[a-zA-Z0-9_\\u4e00-\\u9fa5]+\\]' # 匹配 [表情名]

        return bool(emoji_pattern.search(content)) or bool(re.search(bilibili_emoji_pattern, content))

    def _determine_report_reason_type(self, content, detection_summary):
        """
        根据评论内容和模型检测结果自动判断最合适的举报类型 (增强版)

        Args:
            content (str): 评论内容
            detection_summary (dict): 来自 detect_huawei_fanatic 的检测结果摘要

        Returns:
            int: 举报类型ID
        """
        # 默认使用人身攻击 (4) 或 引战 (7)
        default_reason = 7 # 倾向于引战作为默认值

        # 检查黑名单理由，避免使用失败率高的理由
        blacklisted_reasons = []
        for reason_type, failures in self.backoff_state["reason_failures"].items():
            if failures >= 5:  # 连续5次失败
                blacklisted_reasons.append(reason_type)
                print(f"理由 {reason_type} 在黑名单中，将避免使用")

        # 1. 优先根据模型检测的极端类型判断
        extreme_types = detection_summary.get("extreme_types", [])
        toxic_categories = detection_summary.get("toxicity_details", {}).get("toxic_categories", [])
        matched_patterns = detection_summary.get("matched_patterns", {})

        # 收集候选理由，而不是直接返回
        candidate_reasons = []

        if extreme_types:
            # 强烈暗示人身攻击或违法
            if any(t in extreme_types for t in ["威胁", "严重毒性", "极端言论/诅咒", "身份仇恨"]):
                print("模型检测到严重毒性/威胁/极端言论")
                candidate_reasons.append(4) # 人身攻击
                candidate_reasons.append(1) # 违法违禁
            # 政治相关
            if any(t in extreme_types for t in ["政治敏感", "阴谋论", "民族主义"]):
                 # 如果同时有攻击性言论，优先报攻击
                 if any(t in extreme_types for t in ["竞品攻击", "用户群体攻击", "极端言论/诅咒", "侮辱"]):
                     print("模型检测到政治敏感+攻击，选择[引战(7)]")
                     return 7
                 else:
                     print("模型检测到政治敏感/阴谋论/民族主义，选择[政治敏感(9)]")
                     return 9
            # 引战相关 (竞品攻击, 事故攻击, 用户群体, 泛化, 讽刺)
            if any(t in extreme_types for t in ["竞品攻击", "幸灾乐祸/事故攻击", "用户群体攻击", "泛化攻击", "讽刺/阴阳怪气", "侮辱"]):
                 # 如果匹配了高权重的事故攻击，更倾向引战
                 if "xiaomi_accident_attack" in matched_patterns:
                     print("模型检测到小米事故攻击，选择[引战(7)]")
                     return 7
                 print("模型检测到引战类言论，选择[引战(7)]")
                 return 7
            # 其他如品牌崇拜、技术夸大等，也归为引战
            if any(t in extreme_types for t in ["品牌崇拜", "技术夸大"]):
                 print("模型检测到品牌崇拜/技术夸大，选择[引战(7)]")
                 return 7

        # 2. 如果模型未识别特定类型，回退到关键词/模式匹配 (保留原有逻辑作为补充)
        print("模型未识别特定极端类型或未检测到极端，回退到关键词/模式匹配...")

        # 政治敏感关键词
        political_keywords = [
            "政府", "国家主席", "总书记", "共产党", "民主", "自由", "独立", "台湾", "香港",
            "新疆", "西藏", "法轮", "六四", "天安门", "反华", "反共", "政治", "敏感",
            "国家领导人", "领导人", "主席", "总理", "总统", "爱国", "卖国", "汉奸",
            "民族", "国产", "国货", "中国制造", "中国骄傲", "民族骄傲", "民族品牌"
        ]

        # 色情低俗关键词
        porn_keywords = [
            "色情", "低俗", "黄色", "性感", "诱惑", "裸露", "露点", "露骨", "情色",
            "成人", "av", "porn", "sex", "做爱", "约炮", "一夜情", "嫖娼"
        ]

        # 赌博诈骗关键词
        gambling_keywords = [
            "赌博", "博彩", "彩票", "赌场", "赌钱", "诈骗", "骗钱", "传销", "资金盘",
            "投资回报", "高回报", "快速致富", "一夜暴富", "百分百收益", "稳赚不赔"
        ]

        # 垃圾广告关键词
        ad_keywords = [
            "广告", "推广", "促销", "优惠", "折扣", "限时", "抢购", "秒杀", "联系方式",
            "微信", "QQ", "电话", "加我", "私聊", "私信", "vx", "薇信", "威信"
        ]

        # 引战关键词
        war_keywords = [
            "引战", "吵架", "撕逼", "对立", "骂战", "互喷", "互撕", "杠精", "键盘侠",
            "喷子", "战狼", "粉丝大战", "粉丝互撕", "站队", "挑拨", "挑事", "带节奏",
            "洗地", "水军", "网评员", "公关", "洗白"
        ]

        # 人身攻击关键词
        attack_keywords = [
            "人身攻击", "辱骂", "骂人", "傻逼", "智障", "脑残", "废物", "垃圾", "狗东西",
            "贱人", "婊子", "妓女", "死全家", "去死", "滚蛋", "滚出去", "你妈", "操你",
            "白痴", "蠢货", "猪脑子", "有病", "神经病"
        ]

        # 侵犯隐私关键词
        privacy_keywords = [
            "隐私", "个人信息", "电话号码", "家庭住址", "身份证", "银行卡", "密码",
            "私生活", "偷拍", "偷录", "曝光", "人肉", "扒皮", "扒粪"
        ]

        # 违法违禁关键词
        illegal_keywords = [
            "违法", "违禁", "犯罪", "杀人", "暴力", "恐怖", "血腥", "自杀", "自残",
            "毒品", "枪支", "武器", "爆炸", "炸弹", "制毒", "贩毒", "吸毒"
        ]

        # 剧透关键词
        spoiler_keywords = [
            "剧透", "结局", "死亡", "挂了", "便当", "最后", "结尾", "大结局", "反转",
            "转折", "真相", "真凶", "凶手", "犯人", "身份", "揭露", "揭秘"
        ]

        # 青少年不良信息关键词
        youth_harmful_keywords = [
            "早恋", "辍学", "逃学", "抽烟", "喝酒", "打架", "斗殴", "校园暴力",
            "欺凌", "霸凌", "网瘾", "游戏成瘾", "沉迷", "自残", "厌学"
        ]

        # 计算各类型的匹配分数
        scores = {
            1: sum(1 for kw in illegal_keywords if kw in content),  # 违法违禁
            2: sum(1 for kw in porn_keywords if kw in content),  # 色情低俗
            3: sum(1 for kw in gambling_keywords if kw in content),  # 赌博诈骗
            4: sum(1 for kw in attack_keywords if kw in content),  # 人身攻击
            5: sum(1 for kw in privacy_keywords if kw in content),  # 侵犯隐私
            6: sum(1 for kw in ad_keywords if kw in content),  # 垃圾广告
            7: sum(1 for kw in war_keywords if kw in content),  # 引战
            8: sum(1 for kw in spoiler_keywords if kw in content),  # 剧透
            9: sum(1 for kw in political_keywords if kw in content),  # 政治敏感
            13: sum(1 for kw in youth_harmful_keywords if kw in content) # 青少年不良(使用ID 13)
            # 移除了 ID 11 (不良信息) 和 12 (其他)， 14 (侵犯权益), 15 (违法违规) 的评分逻辑，与已有类别重叠
        }

        # 检查特定模式
        patterns = {
            4: [  # 人身攻击
                r"你.*?(脑残|智障|傻逼|废物|垃圾|滚|有病|白痴)",
                r"(脑残|智障|傻逼|废物|垃圾|有病|白痴).*?的(人|家伙|东西)"
            ],
            7: [  # 引战
                r"(华为|苹果|小米|三星).*?比.*?(华为|苹果|小米|三星).*?(好|强|差|垃圾)",
                r"支持(华为|苹果|小米|三星).*?反对(华为|苹果|小米|三星)",
                r"(华为|苹果|小米|三星)粉.*?(脑残|智障|傻逼)"
            ],
            9: [  # 政治敏感
                r"(美国|西方|外国)(打压|封锁|制裁)(中国|华为)",
                r"华为.*?(民族脊梁|民族之光|国产之光|中国之光)",
                r"支持华为.*?就是支持.*?中国",
                r"不用华为.*?就是.*?(卖国|汉奸)"
            ]
        }

        # 增加模式匹配的分数
        for reason_type, pattern_list in patterns.items():
            for pattern in pattern_list:
                if re.search(pattern, content, re.IGNORECASE):
                    scores[reason_type] += 2

        # 收集候选理由
        candidate_reasons = []

        # 将得分大于0的理由添加到候选列表
        for reason_id, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
            # 检查得分和黑名单
            if score > 0 and not (reason_id in self.backoff_state["reason_failures"] and self.backoff_state["reason_failures"][reason_id] >= 5):
                candidate_reasons.append(reason_id)
                if len(candidate_reasons) >= 3:  # 最多添加3个候选理由
                    break

        # 如果没有候选理由，使用默认值
        if not candidate_reasons:
            print(f"关键词/模式未匹配，使用默认举报原因 [{default_reason}]")
            return default_reason

        # 使用智能选择最佳理由
        best_reason = self._get_best_reason_type(candidate_reasons)

        print(f"从候选理由 {candidate_reasons} 中选择最佳理由: {best_reason} ({self.get_report_reason_name(best_reason)})")
        return best_reason

    def _generate_report_detail(self, content, reason, detection_summary):
        """
        根据恶意评论类型生成举报说明 (高级版)

        Args:
            content (str): 评论内容
            reason (int): 举报原因类型ID
            detection_summary (dict): 来自 detect_huawei_fanatic 的检测结果摘要

        Returns:
            str: 举报说明
        """
        # 举报原因类型对应的说明
        reason_descriptions = self.get_comment_report_reasons() # 获取最新理由列表
        reason_desc = reason_descriptions.get(reason, "其他违规")

        # 根据不同举报理由生成更具针对性的描述
        reason_templates = {
            1: "该评论包含{extreme_types}内容，违反了社区规范中的违法违禁条例。具体表现为：{examples}",
            4: "该评论对{targets}进行了人身攻击，使用了侮辱性词汇如\"{insults}\"，违反了社区和谐氛围。{context_info}",
            7: "该评论故意挑起用户之间的争端，通过{methods}方式引战，破坏了评论区秩序。{pattern_examples}",
            9: "该评论包含敏感内容，将商业话题与敏感话题不当关联，具体表现为：{examples}"
        }

        # 提取关键信息
        extreme_types = detection_summary.get("extreme_types", [])
        matched_patterns = detection_summary.get("matched_patterns", {})
        context_info = detection_summary.get("context_info", {})

        # 提取违规示例
        examples = self._extract_violation_examples(content, matched_patterns)

        # 根据不同的举报理由提取不同的信息
        if reason == 1:  # 违法违禁
            extreme_types_str = "、".join(extreme_types) if extreme_types else "违规"

            # 添加更多违法违禁相关的具体描述
            if "nationalism" in matched_patterns:
                examples += "，将商业话题与民族主义不当关联"
            if "conspiracy_theory" in matched_patterns:
                examples += "，传播未经证实的阴谋论"

        elif reason == 4:  # 人身攻击
            # 提取攻击目标
            targets = self._extract_attack_targets(content, matched_patterns)

            # 提取侮辱性词汇
            insults = self._extract_insults(content)

            # 添加上下文信息
            context_info_str = ""
            if context_info.get("high_extreme_ratio", 0) > 0.3:
                context_info_str = "该用户在多个评论中表现出类似行为。"

        elif reason == 7:  # 引战
            # 提取引战方式
            methods = self._extract_conflict_methods(matched_patterns)

            # 添加具体的引战模式示例
            pattern_examples = ""
            if "competitor_attack" in matched_patterns:
                pattern_examples = "评论中通过贬低竞争品牌来引发争端"
            elif "blind_worship" in matched_patterns:
                pattern_examples = "评论中通过过度吹捧特定品牌引发争端"
            elif "sarcasm_irony" in matched_patterns:
                pattern_examples = "评论使用阴阳怪气的语气引发争端"

        elif reason == 9:  # 敏感内容
            # 提取敏感内容示例
            if "conspiracy_theory" in matched_patterns:
                examples = "传播关于国际政治的阴谋论，如" + examples
            elif "nationalism" in matched_patterns:
                examples = "将商业竞争与国家利益不当关联，如" + examples

        # 根据举报理由选择合适的模板
        template = reason_templates.get(reason, "该评论包含{extreme_types}内容，违反了社区规范。")

        # 填充模板
        extreme_types_str = "、".join(extreme_types) if extreme_types else "违规"
        report_detail = template.format(
            extreme_types=extreme_types_str,
            examples=examples,
            targets=targets if 'targets' in locals() else "用户",
            insults=insults if 'insults' in locals() else "侮辱性词汇",
            methods=methods if 'methods' in locals() else "多种",
            pattern_examples=pattern_examples if 'pattern_examples' in locals() else "",
            context_info=context_info_str if 'context_info_str' in locals() else ""
        )

        # 添加用户历史行为信息（如果有）
        user_history = detection_summary.get("user_history", {})
        if user_history and user_history.get("extreme_ratio", 0) > 0.3:
            report_detail += f" 该用户历史评论中有{user_history['extreme_ratio']*100:.0f}%包含类似违规内容。"

        # 限制举报详情长度
        max_length = 200  # B站举报详情可能有长度限制
        if len(report_detail) > max_length:
            report_detail = report_detail[:max_length-3] + "..."

        return report_detail

    def _extract_violation_examples(self, content, matched_patterns):
        """提取违规示例"""
        examples = []

        # 从匹配的模式中提取示例
        for pattern_type, matches in matched_patterns.items():
            if isinstance(matches, list) and matches:
                for match in matches[:2]:  # 最多取2个例子
                    if isinstance(match, str) and len(match) > 5:  # 只取有意义的长度
                        # 清理匹配文本，去除多余空格和特殊字符
                        cleaned_match = re.sub(r'\s+', ' ', match).strip()
                        if len(cleaned_match) > 5:
                            examples.append(f'"{cleaned_match}"')

        # 如果没有找到匹配，尝试提取内容中的敏感词
        if not examples:
            # 常见违规词列表
            violation_words = {
                "人身攻击": ["垃圾", "傻逼", "脑残", "废物", "滚", "去死", "智障", "蠢货", "白痴"],
                "引战": ["引战", "节奏", "杠精", "撕逼", "互喷", "对立", "挑拨", "洗地", "水军"],
                "敏感内容": ["政治", "民主", "自由", "台湾", "香港", "新疆", "西藏", "法轮", "反华", "反共"]
            }

            for category, words in violation_words.items():
                for word in words:
                    if word in content:
                        # 提取包含违规词的上下文
                        start = max(0, content.find(word) - 10)
                        end = min(len(content), content.find(word) + len(word) + 10)
                        context = content[start:end].replace(word, f"「{word}」")
                        examples.append(f'"{context}"')
                        if len(examples) >= 2:
                            break
                if examples:
                    break

        return "、".join(examples) if examples else "包含违规内容"

    def _extract_attack_targets(self, content, matched_patterns):
        """提取攻击目标"""
        targets = "其他用户"

        # 检查是否攻击特定用户群体
        if "user_group_attack" in matched_patterns:
            if any(term in content.lower() for term in self.fanatic_detector.xiaomi_special_terms):
                targets = "小米用户群体"
            elif any(term in content.lower() for term in self.fanatic_detector.huawei_special_terms):
                targets = "华为用户群体"
            else:
                targets = "特定用户群体"

        # 检查是否包含@用户
        at_pattern = re.compile(r'@([^\s@]+)')
        at_matches = at_pattern.findall(content)
        if at_matches:
            targets = f"用户 @{at_matches[0]}"

        return targets

    def _extract_insults(self, content):
        """提取侮辱性词汇"""
        insult_words = ["垃圾", "傻逼", "脑残", "废物", "滚", "去死", "智障", "蠢货", "白痴",
                       "狗东西", "滚蛋", "有病", "神经病", "贱", "蠢", "笨", "弱智"]

        found_insults = []
        for word in insult_words:
            if word in content:
                found_insults.append(word)
                if len(found_insults) >= 3:  # 最多取3个
                    break

        return "、".join(found_insults) if found_insults else "侮辱性词汇"

    def _extract_conflict_methods(self, matched_patterns):
        """提取引战方式"""
        methods = []

        method_mapping = {
            "competitor_attack": "攻击竞争品牌",
            "blind_worship": "盲目崇拜特定品牌",
            "tech_exaggeration": "过度夸大技术优势",
            "sarcasm_irony": "讽刺/阴阳怪气",
            "xiaomi_accident_attack": "对产品事故幸灾乐祸"
        }

        for pattern_type in matched_patterns:
            if pattern_type in method_mapping:
                methods.append(method_mapping[pattern_type])

        return "、".join(methods) if methods else "挑起品牌之间的对立"

    def get_comment_report_reasons(self):
        """
        获取评论举报理由列表
        Returns:
            dict: 举报理由字典，key为reason_type，value为reason_name
        """
        # 定义默认举报理由字典 (ID 13 是青少年不良)
        default_reasons = {
            1: "违法违禁", 2: "色情低俗", 3: "赌博诈骗", 4: "人身攻击",
            5: "侵犯隐私", 6: "垃圾广告", 7: "引战", 8: "剧透",
            9: "政治敏感", 13: "青少年不良信息",
            # 可以补充其他已知或常用的 ID
            11: "不良内容" # 补充一个常用的
        }
        reasons = default_reasons.copy()

        try:
            # 获取当前登录状态
            if not self.check_login_status():
                print("未登录状态，返回默认举报理由列表")
                return reasons

            # 尝试从API获取最新的举报理由 (这个API可能不再有效或需要特定参数)
            # url = "https://api.bilibili.com/x/v2/reply/report/reasons"
            # headers = { ... }
            # response = self.session.get(url, headers=headers, timeout=10)
            # ... (省略 API 调用逻辑，优先使用硬编码的常见理由) ...
            print("使用预定义的举报理由列表")

        except Exception as e:
            print(f"获取举报理由时出错: {e}")
            print("使用预定义的举报理由列表")

        return reasons

    def get_report_reason_name(self, reason_type):
        """根据举报类型获取举报原因的文字说明"""
        reasons = self.get_comment_report_reasons()
        return reasons.get(reason_type, "未知原因")

    def _get_best_reason_type(self, candidates):
        """根据历史成功率选择最佳举报理由"""
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

    def _update_backoff_state(self, reason_type, success):
        """更新智能退避状态"""
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











    def report_comment(self, oid, rpid, reason_type, detail):
        """举报评论（增强版，包含智能退避机制）"""
        try:
            if not self.check_login_status():
                print("未登录，无法举报评论")
                return {"code": -101, "message": "未登录"}

            if not self.csrf_token:
                print("缺少csrf_token，尝试重新获取...")
                if not self._get_csrf_token():
                    return {"code": -111, "message": "获取csrf_token失败"}

            # 检查是否需要重置退避状态
            current_time = time.time()
            if current_time - self.backoff_state["last_success_time"] > self.report_delay["backoff"]["reset_after"]:
                # 重置退避状态
                self.backoff_state["consecutive_failures"] = 0
                self.backoff_state["current_backoff_time"] = self.report_delay["backoff"]["initial"]
                self.backoff_state["reason_failures"] = {}
                print(f"长时间未成功举报，重置退避状态")

            url = "https://api.bilibili.com/x/v2/reply/report"
            data = {
                "oid": oid,
                "type": 1,  # 1表示视频评论
                "rpid": rpid,
                "reason": reason_type,
                "content": detail,
                "csrf": self.csrf_token
            }

            headers = {
                "User-Agent": self.user_agent,
                "Referer": f"https://www.bilibili.com/video/av{oid}/",
                "Origin": "https://www.bilibili.com",
                "Content-Type": "application/x-www-form-urlencoded"
            }

            # 计算等待时间（考虑智能退避）
            base_wait = random.uniform(self.report_delay['min'], self.report_delay['max'])
            backoff_wait = 0

            # 如果有连续失败，增加退避时间
            if self.backoff_state["consecutive_failures"] > 0:
                backoff_wait = self.backoff_state["current_backoff_time"]
                print(f"检测到连续失败 {self.backoff_state['consecutive_failures']} 次，应用退避时间 {backoff_wait:.1f} 秒")

            # 如果特定理由失败率高，增加额外等待
            reason_failures = self.backoff_state["reason_failures"].get(reason_type, 0)
            reason_wait = 0
            if reason_failures > 2:  # 如果特定理由连续失败超过2次
                reason_wait = min(reason_failures * 5, 60)  # 每次失败增加5秒，最多60秒
                print(f"举报理由 {reason_type} 已连续失败 {reason_failures} 次，增加等待 {reason_wait:.1f} 秒")

            # 总等待时间
            total_wait = base_wait + backoff_wait + reason_wait
            print(f"准备举报评论 rpid={rpid}, reason={reason_type}({self.get_report_reason_name(reason_type)}), detail='{detail}'")
            print(f"等待时间: 基础={base_wait:.1f}秒 + 退避={backoff_wait:.1f}秒 + 理由特定={reason_wait:.1f}秒 = 总计{total_wait:.1f}秒")
            time.sleep(total_wait)

            response = self.session.post(url, data=data, headers=headers, timeout=15)
            result = response.json()

            if result["code"] == 0:
                print(f"举报成功: rpid={rpid}, message='{result.get('message', '成功')}'")
                # 使用智能退避机制更新状态
                self._update_backoff_state(reason_type, True)
                return {"code": 0, "message": "举报成功"}
            else:
                print(f"举报失败: rpid={rpid}, code={result.get('code')}, message='{result.get('message', '未知错误')}'")
                # 使用智能退避机制更新状态
                self._update_backoff_state(reason_type, False)
                return result

        except Exception as e:
            print(f"举报评论 rpid={rpid} 时出错: {e}")
            # 异常也计入失败
            self.backoff_state["consecutive_failures"] += 1
            return {"code": -1, "message": str(e)}

    def auto_report_malicious_comments(self, keyword, video_count=5, comment_pages=2): # 移除 reason_type 参数
        """
        自动搜索并举报恶意评论 (修改)

        Args:
            keyword: 搜索关键词
            video_count: 搜索的视频数量
            comment_pages: 检查的评论页数 (对应 API 的 next 参数，表示要获取多少 '页')

        Returns:
            统计数据
        """
        print(f"\n开始搜索关键词: {keyword}")

        # 检查登录状态
        if not self.check_login_status():
            print("未登录，无法举报评论")
            return None

        # 搜索视频
        videos = self.search_videos(keyword, page=1) # 只需要搜索第一页

        if not videos:
            print(f"搜索关键词 {keyword} 未找到视频")
            return None

        # 统计数据 (更新)
        stats = {
            "keyword": keyword,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "processed_videos": 0,
            "processed_comments": 0,
            "detected_malicious": 0,
            "reported_comments": 0,
            "report_failed": 0,
            "malicious_details": [],
            "total_videos_found": len(videos), # 实际找到的视频数
            "target_videos_process": min(video_count, len(videos)), # 目标处理的视频数
            "total_comments_fetched": 0, # 实际获取到的评论总数
            "extreme_types_stats": {}, # 按极端类型统计
            "report_reason_stats": {} # 按举报原因统计
        }

        # 限制处理的视频数量
        max_videos_to_process = stats["target_videos_process"]
        print(f"找到 {len(videos)} 个视频，将处理前 {max_videos_to_process} 个")

        # 循环处理每个视频
        for video_index, video in enumerate(videos[:max_videos_to_process]):
            try:
                # 获取视频信息
                title = video.get("title", "未知标题")
                author = video.get("author", "未知作者")
                bvid = video.get("bvid", "")
                aid = video.get("aid", "") # search_videos 已处理转换

                # 确保有可用ID
                if not aid: # 优先使用 aid 作为 OID
                    print(f"视频缺少有效 AID，跳过: title='{title}', bvid='{bvid}'")
                    continue

                video_identifier = f"av{aid}" + (f" (BV:{bvid})" if bvid else "")
                oid = str(aid) # OID 通常是 aid

                print(f"\n{'='*10} 处理视频 {video_index+1}/{max_videos_to_process}: {title} {'='*10}")
                print(f"视频ID: {video_identifier}, 作者: {author}, OID: {oid}")

                # 添加随机延迟，模拟人类行为
                delay = random.uniform(2, 4)
                # print(f"等待 {delay:.1f} 秒后获取评论...")
                time.sleep(delay)

                # 获取评论 (使用 next 参数循环获取多页)
                all_comments_for_video = []
                current_page_num = 0 # B站评论 API 的 next 从 0 或 1 开始，模式3 热评分页用 next
                next_page_cursor = 1 # next 参数起始值通常是 1

                for _ in range(comment_pages): # 循环获取指定页数
                    current_page_num += 1
                    print(f"--- 获取评论 第 {current_page_num}/{comment_pages} 页 (next={next_page_cursor}) ---")

                    try:
                        # 获取指定页的评论
                        page_comments = self.get_video_comments(aid, page=next_page_cursor) # 使用 aid 和 next_page_cursor

                        if not page_comments:
                            print(f"视频 {video_identifier} 第 {current_page_num} 页没有评论或已达末页")
                            break # 获取不到评论则停止获取该视频的评论

                        all_comments_for_video.extend(page_comments)
                        stats["total_comments_fetched"] += len(page_comments)
                        next_page_cursor += 1 # next 参数递增

                        print(f"获取到 {len(page_comments)} 条评论 (本视频累计: {len(all_comments_for_video)})")

                        # 页面之间添加随机延迟
                        if current_page_num < comment_pages:
                            delay = random.uniform(2, 4)
                            # print(f"等待 {delay:.1f} 秒后获取下一页...")
                            time.sleep(delay)

                    except Exception as e:
                        print(f"获取评论页时出错: {e}")
                        break # 出错则停止获取该视频的评论

                # 如果获取评论失败或没有评论，继续处理下一个视频
                if not all_comments_for_video:
                    print(f"视频 {video_identifier} 没有获取到任何评论，继续处理下一个视频")
                    continue

                # 更新处理的评论总数
                stats["processed_comments"] += len(all_comments_for_video)
                stats["processed_videos"] += 1

                print(f"--- 开始分析本视频的 {len(all_comments_for_video)} 条评论 ---")

                # 检测恶意评论并举报
                reported_rpids_in_video = set() # 防止重复举报同一个评论

                # 创建列表来存储检测到的恶意评论，用于后续排序
                detected_malicious_comments = []

                print(f"--- 第一阶段: 检测所有评论 ---")

                for comment_index, comment in enumerate(tqdm(all_comments_for_video, desc=f"分析评论 av{aid}", unit="条")):
                    try:
                        # 安全获取评论内容和各种ID
                        content = ""
                        rpid = 0
                        mid = 0
                        uname = ""
                        parent = 0  # 父评论ID，用于上下文分析
                        root = 0    # 根评论ID，用于上下文分析
                        like_count = 0  # 点赞数，用于优先级排序

                        # 安全获取各字段
                        if isinstance(comment, dict):
                            rpid = comment.get("rpid", 0)
                            mid = comment.get("mid", 0)
                            parent = comment.get("parent", 0)
                            root = comment.get("root", 0)
                            like_count = comment.get("like", 0)

                            # 安全获取评论内容
                            content_obj = comment.get("content")
                            if isinstance(content_obj, dict) and "message" in content_obj:
                                content = content_obj.get("message", "")
                            elif isinstance(content_obj, str):
                                content = content_obj
                            else:
                                content = str(content_obj) if content_obj else ""

                            # 安全获取用户名
                            member_obj = comment.get("member")
                            if isinstance(member_obj, dict) and "uname" in member_obj:
                                uname = member_obj.get("uname", "")
                            else:
                                uname = comment.get("uname", "未知用户")

                        # 跳过无内容或无ID或已举报的评论
                        if not content or not rpid or rpid in reported_rpids_in_video:
                            continue

                        # === 调用模型进行检测 ===
                        # print(f"\n检测评论 rpid={rpid}, user='{uname}', content='{content[:50]}...'") # 减少打印
                        detection_result = self.fanatic_detector.detect_huawei_fanatic(content, rpid, mid)
                        is_extreme = detection_result.get("is_huawei_fanatic", False)
                        confidence = detection_result.get("confidence", 0.0)
                        detection_summary = detection_result.get("detection_summary", {})

                        # 如果启用了上下文分析，考虑视频标题和其他评论
                        if self.context_analysis_enabled and is_extreme:
                            context_score, context_info = self.fanatic_detector.analyze_comment_context(comment, title, all_comments_for_video)
                            # 如果上下文得分较高，增加置信度
                            if context_score > 0.5:
                                confidence = min(confidence + context_score * 0.2, 1.0)  # 最多增加20%置信度
                                print(f"  上下文分析: 得分={context_score:.2f}, 置信度提升至{confidence:.2f}")
                                # 将上下文信息添加到检测摘要中
                                detection_summary["context_info"] = context_info

                        # 如果可能是极端粉丝，分析用户历史行为
                        if is_extreme and mid > 0:
                            # 获取用户历史评论
                            user_comments = self.get_user_comments(mid, max_count=20)
                            if user_comments:
                                # 分析用户行为
                                fanatic_score, user_stats = self.fanatic_detector.analyze_user_behavior(mid, user_comments)
                                # 如果用户行为分数较高，增加置信度
                                if fanatic_score > 0.5:
                                    confidence = min(confidence + fanatic_score * 0.15, 1.0)  # 最多增加15%置信度
                                    print(f"  用户行为分析: 得分={fanatic_score:.2f}, 置信度提升至{confidence:.2f}")
                                    # 将用户行为信息添加到检测摘要中
                                    detection_summary["user_history"] = user_stats

                        if is_extreme:
                            stats["detected_malicious"] += 1
                            print(f"\n检测到恶意评论! (rpid={rpid}, user='{uname}', conf={confidence:.2f})")
                            print(f"  内容: {content}")
                            reasoning = detection_summary.get("reasoning", "N/A")
                            extreme_types = detection_summary.get("extreme_types", [])
                            print(f"  理由: {reasoning}")
                            if extreme_types:
                                print(f"  类型: {', '.join(extreme_types)}")
                                # 统计极端类型
                                for etype in extreme_types:
                                    stats["extreme_types_stats"][etype] = stats["extreme_types_stats"].get(etype, 0) + 1

                            # 将检测到的恶意评论添加到列表中，用于后续排序
                            detected_malicious_comments.append({
                                "rpid": rpid,
                                "mid": mid,
                                "uname": uname,
                                "content": content,
                                "confidence": confidence,
                                "detection_summary": detection_summary,
                                "like_count": like_count,
                                "parent": parent,
                                "root": root
                            })

                            # 记录详细信息 (简化)
                            stats["malicious_details"].append({
                                "video_id": video_identifier,
                                "video_title": title,
                                "comment_rpid": rpid,
                                "comment_content": content,
                                "user_name": uname,
                                "confidence": confidence,
                                "extreme_types": extreme_types,
                                "reasoning": reasoning,
                                "report_reason": reason_name if 'reason_name' in locals() else "未知",
                                "report_detail": report_detail if 'report_detail' in locals() else ""
                            })

                    except Exception as e:
                        print(f"处理评论时出错: {e}")
                        continue

                # 第二阶段：按优先级排序恶意评论并举报
                if detected_malicious_comments:
                    print(f"\n--- 第二阶段: 按优先级排序并举报 ({len(detected_malicious_comments)} 条恶意评论) ---")

                    # 计算每条评论的优先级分数
                    for comment in detected_malicious_comments:
                        priority_score = self.fanatic_detector.calculate_report_priority(comment, {
                            "confidence": comment["confidence"],
                            "detection_summary": comment["detection_summary"]
                        })
                        comment["priority_score"] = priority_score

                    # 按优先级分数排序
                    detected_malicious_comments.sort(key=lambda x: x["priority_score"], reverse=True)

                    # 限制每个视频的举报数量
                    max_reports_per_video = min(len(detected_malicious_comments), 10)  # 每个视频最多举报10条

                    for i, comment in enumerate(detected_malicious_comments[:max_reports_per_video]):
                        rpid = comment["rpid"]
                        content = comment["content"]
                        confidence = comment["confidence"]
                        detection_summary = comment["detection_summary"]

                        # 如果已经举报过，跳过
                        if rpid in reported_rpids_in_video:
                            continue

                        priority_score = comment.get("priority_score", 0)
                        print(f"\n处理排序后的恶意评论 {i+1}/{max_reports_per_video} (rpid={rpid}, 优先级={priority_score:.2f}, 置信度={confidence:.2f})")
                        print(f"  内容: {content}")

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

            except Exception as e:
                print(f"处理视频时出错: {e}")
                continue

        # 保存统计信息
        log_file = self.save_report_log(stats, keyword)

        # 打印统计结果
        print("\n" + "="*50)
        print("华为极端粉丝评论检测统计结果")
        print("="*50)
        print(f"搜索关键词: {keyword}")
        print(f"检测时间: {stats['time']}")
        print(f"处理视频数: {stats['processed_videos']}/{stats['total_videos']}")
        print(f"总评论数: {stats['total_comments']}")
        print(f"检测到华为极端粉丝评论数: {stats['detected_malicious']}")
        print(f"成功举报数: {stats['reported_comments']}")
        print(f"举报失败数: {stats['report_failed']}")

        print("\n检测方法统计:")
        print(f"  - 传统规则: {stats['detection_method_stats']['traditional_only']} 条")
        print(f"  - 大模型: {stats['detection_method_stats']['llm_only']} 条")
        print(f"  - 两种方法都检测到: {stats['detection_method_stats']['both_methods']} 条")

        if stats["llm_categories_stats"]:
            print("\n大模型检测类别分布:")
            for category, count in sorted(stats["llm_categories_stats"].items(), key=lambda x: x[1], reverse=True):
                print(f"  - {category}: {count} 条")

        if stats["extreme_types_stats"]:
            print("\n极端特征分布:")
            for etype, count in sorted(stats["extreme_types_stats"].items(), key=lambda x: x[1], reverse=True):
                print(f"  - {etype}: {count} 条")

        if stats["malicious_details"]:
            print("\n检测到的华为极端粉丝评论样本:")
            for i, detail in enumerate(stats["malicious_details"][:5]):  # 只显示前5条
                print(f"{i+1}. {detail['user_name']}: {detail['comment_content'][:50]}..." if len(detail['comment_content']) > 50 else f"{i+1}. {detail['user_name']}: {detail['comment_content']}")
                print(f"   检测方法: {detail['detection_method']}")
                print(f"   检测理由: {detail['reasoning']}")
                print(f"   置信度: {detail['confidence']:.2f}")
                print("")

            if len(stats["malicious_details"]) > 5:
                print(f"... 还有 {len(stats['malicious_details']) - 5} 条评论详情未显示 ...")

        print(f"\n详细报告已保存至: {log_file}")

        return stats

    def save_report_log(self, stats, keyword):
        """保存举报日志"""
        try:
            # 创建logs目录（如果不存在）
            if not os.path.exists("logs"):
                os.makedirs("logs")

            # 创建文件名，使用时间和关键词
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"logs/report_log_{timestamp}_{keyword}.json"

            # 保存到文件
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(stats, f, ensure_ascii=False, indent=2)

            print(f"报告已保存至: {filename}")
            return filename
        except Exception as e:
            print(f"保存报告时出错: {e}")
            return None

    def _analyze_comment_sentiment(self, content):
        """分析评论情感强度"""
        if not content:
            return 0

        # 简单实现，计算情感词数量和强度
        sentiment_score = 0

        # 计算正面情感词
        positive_count = sum(content.count(word) for word in self.positive_words)
        sentiment_score += positive_count * 1

        # 计算负面情感词
        negative_count = sum(content.count(word) for word in self.negative_words)
        sentiment_score += negative_count * 1.5  # 负面情感权重较高

        # 计算极端标记词
        extreme_count = sum(content.count(word) for word in self.extreme_markers)
        sentiment_score += extreme_count * 0.5

        # 计算强度词
        for marker, score in self.intensity_markers.items():
            if marker in content:
                sentiment_score += score * 0.5

        # 计算感叹号和问号
        exclamation_count = content.count('!') + content.count('！')
        sentiment_score += exclamation_count * 0.5

        question_count = content.count('?') + content.count('？')
        sentiment_score += question_count * 0.3

        # 评论长度因子
        length_factor = min(len(content) / 50, 2)  # 最大加成2分
        sentiment_score += length_factor

        return sentiment_score

    def _check_extreme_patterns(self, content):
        """检查极端表达模式"""
        patterns = [
            r"(最|最最)(好|棒|强|烂|差|坏)",
            r"(没有|不是)(之一)",
            r"(宇宙|天下|世界|全球|无敌)(第一|最强|最好|最差)",
            r"吊打.*全部",
            r"秒杀.*所有",
            r"(碾压|吊打|秒杀|暴打)(一切|全部|所有)",
            r"(没有)(任何|一点|丝毫)(优点|缺点|问题|长处|短处)",
            r"(完全|彻底|绝对)(垃圾|领先|落后|无敌)",
            r"(从来|永远)(不会|不可能)",
            r"买(就|必须|一定)买",
            r"(一定|必须|肯定|绝对)(不要|不能|要)(买|选)"
        ]

        detected_patterns = []
        for pattern in patterns:
            if re.search(pattern, content):
                detected_patterns.append(pattern)

        return detected_patterns

    def llm_based_fanaticism_detection(self, content):
        """
        基于大模型技术的极端粉丝言论检测

        Args:
            content: 评论内容

        Returns:
            tuple: (是否为极端言论, 详细信息)
        """
        try:
            if not content or len(content.strip()) < 5:  # 内容太短不做分析
                return False, {}

            # 初始化分析结果
            result = {
                "is_extreme": False,
                "score": 0.0,
                "categories": [],
                "keywords": [],
                "reasoning": "",
                "confidence": 0.0
            }

            # 特征向量化
            feature_weights = {
                # 品牌对比特征
                "brand_comparison": {
                    "keywords": ["华为", "小米", "苹果", "三星", "鸿蒙", "iOS", "安卓", "MIUI"],
                    "patterns": [
                        (r"华为.*?比.*?小米.*?(好|强|厉害)", 1.5),
                        (r"小米.*?比.*?华为.*?(差|弱|垃圾)", 1.6),
                        (r"华为.*?超越.*?苹果", 1.3),
                        (r"华为.*?领先.*?全球", 1.4),
                        (r"鸿蒙.*?比.*?(安卓|iOS).*?先进", 1.5)
                    ],
                    "weight": 0.8
                },
                # 极端情绪特征
                "extreme_emotion": {
                    "keywords": ["无敌", "最强", "第一", "吊打", "碾压", "秒杀", "超越", "领先"],
                    "patterns": [
                        (r"华为.*?(无敌|最强|第一|吊打|碾压|秒杀)", 1.7),
                        (r"[^不没].*(遥遥领先)", 1.8),
                        (r"华为.*?天下第一", 2.0),
                        (r"华为.*?宇宙第一", 2.0)
                    ],
                    "weight": 1.0
                },
                # 国家民族情绪特征
                "nationalism": {
                    "keywords": ["中国", "民族", "国产", "爱国", "自主", "国家", "卖国", "汉奸"],
                    "patterns": [
                        (r"支持华为.*?爱国", 1.8),
                        (r"用华为.*?爱国", 1.8),
                        (r"华为.*?民族的骄傲", 1.6),
                        (r"不用华为.*?就是.*?(卖国|汉奸)", 2.0),
                        (r"用(苹果|小米).*?(卖国|汉奸)", 2.0),
                        (r"华为.*?国家的希望", 1.5)
                    ],
                    "weight": 1.2
                },
                # 阴谋论特征
                "conspiracy": {
                    "keywords": ["打压", "封锁", "制裁", "勾结", "合作", "妥协", "收集", "监控", "隐私", "美国"],
                    "patterns": [
                        (r"美国.*?打压.*?华为", 1.4),
                        (r"西方.*?封锁.*?华为", 1.4),
                        (r"小米.*?勾结.*?美国", 1.9),
                        (r"雷军.*?向美国.*?妥协", 1.8),
                        (r"小米.*?(收集|窃取).*?(数据|隐私)", 1.7)
                    ],
                    "weight": 1.1
                },
                # 攻击竞品特征
                "competitor_attack": {
                    "keywords": ["垃圾", "渣", "差", "烂", "辣鸡", "骗子", "智商税", "山寨", "抄袭"],
                    "patterns": [
                        (r"小米.*?(垃圾|渣|差|烂|辣鸡)", 1.6),
                        (r"雷军.*?(垃圾|无能|骗子)", 1.8),
                        (r"小米.*?智商税", 1.5),
                        (r"小米.*?(山寨|抄袭).*?华为", 1.7),
                        (r"雷军.*?(抄袭|模仿).*?任正非", 1.7)
                    ],
                    "weight": 1.0
                },
                # 人身攻击特征
                "personal_attack": {
                    "keywords": ["脑残", "智障", "傻逼", "废物", "狗东西", "蠢货", "猪脑子", "没脑子", "眼瞎"],
                    "patterns": [
                        (r"米粉.*?(脑残|智障|傻逼|蠢货|猪脑子)", 1.9),
                        (r"用小米的.*?(没脑子|智商|眼瞎)", 1.9),
                        (r"小米的粉丝.*?都是.*?傻", 1.8)
                    ],
                    "weight": 1.3
                }
            }

            # 获取之前的函数剩余代码并返回一个合理的结果
            return False, result

        except Exception as e:
            print(f"LLM极端粉丝检测出错: {str(e)}")
            return False, {}

    def enhanced_extreme_fan_detection(self, content):
        """
        增强版华为极端粉丝检测，结合传统规则和大模型分析

        Args:
            content: 评论内容

        Returns:
            tuple: (是否为极端粉丝, 详细信息)
        """
        # 1. 先使用传统规则检测
        is_traditional_extreme, traditional_result = self._is_huawei_fanatic_comment(content)

        # 2. 使用大模型检测
        is_llm_extreme, llm_result = self.llm_based_fanaticism_detection(content)

        # 3. 结果融合
        is_extreme = is_traditional_extreme or is_llm_extreme

        # 如果两个模型都返回了极端的结果，提高置信度
        confidence = 0.0
        if is_traditional_extreme and is_llm_extreme:
            confidence = min(0.95, (traditional_result.get("score", 0) / 4.0 + llm_result.get("confidence", 0)) / 2 + 0.2)
        elif is_traditional_extreme:
            confidence = min(0.9, traditional_result.get("score", 0) / 4.0)
        elif is_llm_extreme:
            confidence = llm_result.get("confidence", 0)

        # 4. 融合后的判断理由
        reasoning = ""
        if is_traditional_extreme:
            reasoning = traditional_result.get("reason", "传统规则识别为极端言论")

        if is_llm_extreme:
            llm_reasoning = llm_result.get("reasoning", "")
            if reasoning:
                reasoning += f"；大模型分析: {llm_reasoning}"
            else:
                reasoning = f"大模型分析: {llm_reasoning}"

        # 5. 整合检测结果
        result = {
            "is_extreme": is_extreme,
            "confidence": confidence,
            "reasoning": reasoning,
            "traditional_score": traditional_result.get("score", 0) if is_traditional_extreme else 0,
            "llm_score": llm_result.get("score", 0) if is_llm_extreme else 0,
            "categories": llm_result.get("categories", []) if is_llm_extreme else [],
            "keywords": llm_result.get("keywords", []) if is_llm_extreme else [],
            "combined_score": (traditional_result.get("score", 0) / 4.0 + llm_result.get("score", 0) / 3.0) if is_extreme else 0
        }

        return is_extreme, result

def main():
    """主函数"""
    print("=" * 50)
    print("B站恶意评论自动检测与举报工具")
    print("=" * 50)

    # 创建检测器实例
    detector = BilibiliCommentDetector()

    # 检查登录状态
    if not detector.check_login_status():
        print("请先登录B站账号")
        return

    # 获取搜索关键词
    keyword = input("请输入要搜索的关键词: ")

    # 设置参数
    max_videos = int(input("请输入要分析的最大视频数(建议5-10): "))
    max_comments = int(input("请输入每个视频要分析的最大评论数(建议20-50): "))

    # 开始自动搜索和分析
    stats = detector.auto_report_malicious_comments(keyword, max_videos, max_comments)


if __name__ == "__main__":
    main()


