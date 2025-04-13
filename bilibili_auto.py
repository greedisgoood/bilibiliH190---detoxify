#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import time
import random
import requests
import re
import traceback
from dotenv import load_dotenv

class BilibiliAuto:
    """
    Bilibili自动化工具：登录、搜索视频、点赞、评论、举报
    """
    
    def __init__(self):
        # 加载环境变量
        load_dotenv()
        
        # 设置请求头
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        
        # 从环境变量或配置文件加载cookie
        self.cookies = self._load_cookies()
        
        # 会话对象
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.user_agent,
            "Referer": "https://www.bilibili.com",
            "Origin": "https://www.bilibili.com"
        })
        
        # 设置cookies
        if self.cookies:
            self._set_cookies()
            
        # 举报延时配置
        self.report_delay = {
            "min": 3,  # 最小延时（秒）
            "max": 8,  # 最大延时（秒）
            "random": True  # 是否使用随机延时
        }
        
        # 举报频率限制
        self.report_limit = {
            "hourly": 20,  # 每小时最大举报次数
            "daily": 100,  # 每天最大举报次数
            "cooldown": 60  # 连续举报冷却时间（秒）
        }
        
        # 举报记录
        self.report_history = {
            "hourly": [],  # 每小时举报记录
            "daily": []    # 每天举报记录
        }
        
        # 恶意评论关键词分类
        self.malicious_keywords = {
            'insult': [  # 侮辱性词汇
                "傻逼", "垃圾", "废物", "脑残", "智障", "滚蛋", "去死", "混蛋", 
                "白痴", "蠢货", "垃圾视频", "恶心", "辣鸡", "骗子", "骗粉", 
                "弱智", "猪脑子", "狗东西", "猪狗不如", "人渣", "垃圾玩意",
                "废柴", "饭桶", "蠢材", "废话", "放屁", "放狗屁"
            ],
            'discrimination': [  # 歧视性词汇
                "低能", "残废", "瘸子", "聋子", "瞎子", "哑巴", "井底之蛙",
                "乡巴佬", "土包子", "穷鬼", "穷逼", "穷酸", "屌丝"
            ],
            'defamation': [  # 诽谤性词汇
                "抄袭", "剽窃", "水平差", "没素质", "没水平", "没技术", 
                "没才华", "没能力", "没文化", "没教养", "没道德", "没良心",
                "造假", "作假", "冒充", "虚假", "骗流量", "蹭热度"
            ],
            'provocation': [  # 挑衅性词汇
                "滚出", "滚开", "滚远点", "爬", "爬远点", "爬开", 
                "爬出去", "爬走", "爬远一点", "爬一边去", "爬回去",
                "约架", "单挑", "干一架", "干一仗"
            ],
            'spam': [  # 垃圾广告
                "加群", "加微信", "加QQ", "私聊", "私信", "联系方式",
                "推广", "广告", "优惠", "折扣", "特价", "促销"
            ]
        }
        
        # 华为相关关键词
        self.keywords = {
            "huawei_context": [  # 华为相关上下文
                "华为", "鸿蒙", "麒麟", "余承东", "任正非", "徐直军", "方舟编译器",
                "昇腾", "昇麒", "鲲鹏", "海思", "HMS", "EMUI", "HarmonyOS",
                "华为手机", "华为平板", "华为笔记本", "华为手表", "华为耳机",
                "华为生态", "华为系统", "华为芯片", "华为技术", "华为创新"
            ],
            "competitor": [  # 竞争对手
                "苹果", "iPhone", "iOS", "三星", "Galaxy", "小米", "OPPO", "vivo", 
                "谷歌", "Google", "安卓", "Android", "高通", "联发科", "英特尔",
                "微软", "Windows", "索尼", "索尼手机", "索尼相机", "索尼电视"
            ],
            "fanatic": [  # 极端粉丝特征词
                "遥遥领先", "世界第一", "全球领先", "无人能敌", "傲视群雄",
                "完爆", "秒杀", "碾压", "吊打", "完胜", "完虐",
                "不买华为就是汉奸", "不用华为就是不爱国", "华为就是中国",
                "华为就是民族的骄傲", "华为就是国家的骄傲",
                "华为就是未来", "华为就是希望", "华为就是信仰",
                "华为就是情怀", "华为就是骄傲", "华为就是自豪",
                "华为就是荣耀", "华为就是辉煌", "华为就是传奇"
            ],
            "conspiracy": [  # 阴谋论相关
                "美国打压", "美国制裁", "美国封锁", "美国害怕", "美国恐惧",
                "美国嫉妒", "西方打压", "西方制裁", "西方封锁",
                "技术封锁", "技术打压", "技术制裁", "芯片封锁",
                "系统封锁", "生态封锁", "市场封锁", "供应链封锁",
                "政治打压", "政治迫害", "政治陷害", "政治迫使"
            ]
        }
        
        # 基础URL
        self.base_url = "https://api.bilibili.com"
        self.search_url = "https://api.bilibili.com/x/web-interface/wbi/search/type"
        self.like_url = "https://api.bilibili.com/x/web-interface/archive/like"
        self.comment_url = "https://api.bilibili.com/x/v2/reply/add"
        self.report_url = "https://api.bilibili.com/x/web-interface/archive/report"
        self.comment_list_url = "https://api.bilibili.com/x/v2/reply/main"
        self.report_comment_url = "https://api.bilibili.com/x/v2/reply/report"
        
        # 消息相关URL
        self.reply_me_url = "https://api.bilibili.com/x/msgfeed/reply"
        
        # 恶意评论正则表达式（按类型分类）
        self.malicious_patterns = {
            'insult': [
                r"[你他][\s\S]{0,3}[妈马麻吗][\s\S]{0,3}[的地得]",  # 你妈的变种
                r"[草操艹日][\s\S]{0,2}[你他它她]",  # 操你变种
                r"[傻煞沙][比逼笔屄]",  # 傻逼变种
                r"[我卧][日操草艹][了啦辣]",  # 我操了变种
                r"[垃拉辣][圾级鸡叽]",  # 垃圾变种
                r"[废费][物务]",  # 废物变种
                r"[脑闹][残惨]",  # 脑残变种
                r"[智知][障章]",  # 智障变种
                r"[混浑][蛋旦]",  # 混蛋变种
                r"[白百][痴痴]",  # 白痴变种
                r"[蠢春][货伙]",  # 蠢货变种
                r"[猪豬珠][脑腦惱]",  # 猪脑变种
                r"[狗狗gou][东東]",  # 狗东变种
            ],
            'discrimination': [
                r"[低底][能能]",  # 低能变种
                r"[穷窮][鬼gui]",  # 穷鬼变种
                r"[屌吊][丝絲]",  # 屌丝变种
            ],
            'defamation': [
                r"[抄钞][袭襲]",  # 抄袭变种
                r"[骗騙][子仔]",  # 骗子变种
            ],
            'threat': [
                r"[打拍][死死si]",  # 打死变种
                r"[干幹][死死si]",  # 干死变种
            ],
            'fanatic': [
                r"[美米][帝蒂][良亮]心",  # 美帝良心变种
                r"[工工][业業][之之][光光]",  # 工业之光变种
                r"[民民][族族][脊脊][梁梁]",  # 民族脊梁变种
                r"[卖卖売][国國]",  # 卖国变种
                r"[汉漢][奸姦]",  # 汉奸变种
                r"[美米][分份狗]",  # 美分/美狗变种
                r"[洋羊][奴努]",  # 洋奴变种
                r"[跪跪][舔舐]",  # 跪舔变种
                r"[崇崇][洋羊][媚媚][外外]",  # 崇洋媚外变种
                r"[自自][主主][创創][新新]",  # 自主创新变种
                r"[领領][先先][全全][球球]",  # 领先全球变种
                r"[断斷][供供]",  # 断供变种
                r"[卡卡][脖脖][子子]",  # 卡脖子变种
                r"[霸霸][权權]",  # 霸权变种
                r"[倒倒][闭閉]",  # 倒闭变种
                r"[爱愛][国國][者者]",  # 爱国者变种
                r"[自自][研硏]",  # 自研变种
                r"[米米][猴猴侯候]",  # 米猴变种
                r"[米米][狗狗]",  # 米狗变种
                r"[米米][蛆蛆]",  # 米蛆变种
                r"[果菓][蛆蛆]",  # 果蛆变种
                r"[猕猕][猴猴侯候]",  # 猕猴变种
                r"[糇糇][货貨]",  # 糇货变种
                r"[殖植][人仁]",  # 殖人变种
                r"[殖植][货貨]",  # 殖货变种
                r"[殖植][民民]",  # 殖民变种
                r"[洋羊][垃拉][圾級]",  # 洋垃圾变种
                r"[洋羊][鬼鬼][子子]",  # 洋鬼子变种
                r"[自自][主主][可可][控控]",  # 自主可控变种
                r"[国國][产產][自自][主主]",  # 国产自主变种
                r"[全全][自自][研硏]",  # 全自研变种
                r"[核核][心芯][科科][技技]",  # 核心科技变种
                r"[民民][族族][品品][牌牌]",  # 民族品牌变种
                r"[爱愛][国國][品品][牌牌]",  # 爱国品牌变种
                r"[土土][殖植]",  # 土殖变种
                r"[韩韓][狗狗]",  # 韩狗变种
                r"[日日][狗狗]",  # 日狗变种
                r"[印印][狗狗]",  # 印狗变种
                r"[欧歐][狗狗]",  # 欧狗变种
                r"[美美][狗狗]",  # 美狗变种
                r"[韩韓][奴奴]",  # 韩奴变种
                r"[日日][奴奴]",  # 日奴变种
                r"[印印][奴奴]",  # 印奴变种
                r"[欧歐][奴奴]",  # 欧奴变种
                r"[美美][奴奴]",  # 美奴变种
                r"[舔舔][韩韓]",  # 舔韩变种
                r"[舔舔][日日]",  # 舔日变种
                r"[媚媚][韩韓]",  # 媚韩变种
                r"[媚媚][日日]",  # 媚日变种
                r"[跪跪][韩韓]",  # 跪韩变种
                r"[跪跪][日日]",  # 跪日变种
                r"[棒棒][子子]",  # 棒子变种
                r"[阿阿][三三]",  # 阿三变种
                r"[倭倭][寇寇]"   # 倭寇变种
            ],
            'army_terms': [
                r"[水水][军軍]",  # 水军变种
                r"[带帶][节節][奏奏]",  # 带节奏变种
                r"[洗洗][地地]",  # 洗地变种
                r"[五五][毛毛]",  # 五毛变种
                r"[美美][分分]",  # 美分变种
                r"[狗狗][腿腿][子子]",  # 狗腿子变种
                r"[走走][狗狗]",  # 走狗变种
                r"[职職][业業][黑黑]",  # 职业黑变种
                r"[职職][业業][吹吹]",  # 职业吹变种
                r"[职職][业業][粉粉]",  # 职业粉变种
                r"[职職][业業][喷噴]",  # 职业喷变种
                r"[职職][业業][杠杠]",  # 职业杠变种
                r"[职職][业業][洗洗]"   # 职业洗变种
            ],
            'huawei_fanatic': [
                r"华为[比跟和].*?[强好领优]",  # 华为比xxx强
                r"[支持力挺]华为.*?到底",  # 支持华为到底
                r"华为.*?[赢胜超越]",  # 华为xxx赢
                r"[美米日韩].*?[垃圾废物渣]",  # 美/米/日/韩xxx垃圾
                r"[苹果三星小米].*?[抄袭山寨盗版]",  # 其他品牌抄袭
                r"华为.*?[领先超越].*?\d+年",  # 华为领先xx年
                r"[美国西方洋人].*?[亡完蛋衰落]",  # 美国/西方要完蛋
                r"[跪舔媚外洋奴].*?[苹果三星谷歌]",  # 跪舔外国品牌
                r"[芯片技术].*?[断供封锁制裁]",  # 芯片/技术断供/封锁
                r"华为.*?[自主研发自研].*?[领先世界]",  # 华为自研领先世界
                r"华为.*?[吊打碾压].*?[苹果三星小米]",  # 华为吊打其他品牌
                r"[美帝鬼子洋人].*?[亡完蛋死]",  # 极端民族主义
                r"[国产自主].*?[崛起胜利]",  # 过度民族主义
                r"华为.*?[统治支配].*?[市场江湖]"  # 市场夸大
            ]
        }
        
        # 评论评分权重
        self.score_weights = {
            'insult': 3.0,        # 侮辱性词汇权重
            'discrimination': 2.5, # 歧视性词汇权重
            'defamation': 2.0,    # 诽谤性词汇权重
            'provocation': 1.5,   # 挑衅性词汇权重
            'spam': 1.0,          # 垃圾广告权重
            'threat': 3.5,        # 威胁性词汇权重
            'fanatic': 2.0,       # 极端粉丝言论权重
            'extreme_behavior': 2.5,  # 极端行为权重
            'conspiracy': 2.0,     # 阴谋论权重
            'pattern_match': 2.0,  # 正则匹配权重
            'length_penalty': 0.1, # 长度惩罚系数（较短评论的惩罚）
            'repeat_penalty': 0.5, # 重复字符惩罚系数
            
            # 新增的细分权重
            'brand_worship': 1.5,  # 品牌崇拜权重
            'tech_exaggeration': 2.0,  # 技术夸大权重
            'nationalism': 2.5,    # 民族主义情绪权重
            'product_attack': 2.0, # 贬低竞品权重
            'conspiracy_theory': 2.5,  # 阴谋论权重
            'blind_worship': 1.5,  # 盲目崇拜权重
            'extreme_opposition': 2.5,  # 极端对立权重
            'market_exaggeration': 1.5,  # 市场夸大权重
            'emotional_content': 1.0,  # 情感化内容权重
            
            # 针对小米的攻击权重
            'xiaomi_attack': 3.0,  # 针对小米的攻击权重
            'xiaomi_personal_attack': 3.5,  # 针对雷军个人的攻击权重
            'xiaomi_tech_mock': 2.5,  # 针对小米技术的嘲讽权重
            'xiaomi_marketing_mock': 2.0,  # 针对小米营销的嘲讽权重
            
            # 组合效应权重（当多个类别同时出现时的额外权重）
            'combined_effect': 0.5,  # 多类别组合效应权重
            
            'huawei_fanatic': 3.0,  # 华为极端粉丝言论权重
            'huawei_brand_worship': 2.0,  # 华为品牌盲目崇拜权重
            'huawei_tech_exaggeration': 2.5,  # 华为技术夸大权重
            'huawei_nationalism': 3.0,  # 华为相关民族主义情绪权重
            'huawei_conspiracy': 2.5,  # 华为相关阴谋论权重
            'huawei_opposition': 3.0,  # 华为相关极端对立言论权重
            'context_bonus': 0.5,  # 上下文组合加成权重
        }
        
        # 恶意评论判定阈值
        self.malicious_threshold = 3.0  # 超过此分数将被判定为恶意评论
        
        # 组合效应阈值（出现多少个不同类别时触发组合效应）
        self.combination_threshold = 2
    
    def _load_cookies(self):
        """从环境变量或cookie文件加载cookies"""
        # 优先从环境变量加载
        cookie_str = os.getenv("BILIBILI_COOKIE")
        if cookie_str:
            return self._parse_cookie_string(cookie_str)
        
        # 从文件加载
        cookie_file = os.getenv("COOKIE_FILE", "cookies.json")
        if os.path.exists(cookie_file):
            try:
                with open(cookie_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"加载cookie文件失败: {e}")
        
        return None
    
    def _parse_cookie_string(self, cookie_str):
        """解析cookie字符串为字典"""
        cookies = {}
        for item in cookie_str.split("; "):
            if "=" in item:
                key, value = item.split("=", 1)
                cookies[key] = value
        return cookies
    
    def _set_cookies(self):
        """设置cookies到会话"""
        if isinstance(self.cookies, dict):
            self.session.cookies.update(self.cookies)
        else:
            print("Cookie格式错误，请检查")
    
    def check_login_status(self):
        """检查登录状态"""
        try:
            nav_url = "https://api.bilibili.com/x/web-interface/nav"
            response = self.session.get(nav_url)
            data = response.json()
            
            if data["code"] == 0 and data["data"]["isLogin"]:
                print(f"登录成功! 用户名: {data['data']['uname']}")
                return True
            else:
                print(f"登录失败: {data}")
                return False
        except Exception as e:
            print(f"检查登录状态时出错: {e}")
            return False
    
    def get_replies_to_me(self, page=1, page_size=20):
        """
        获取回复我的评论
        
        Args:
            page: 页码
            page_size: 每页数量
            
        Returns:
            回复列表
        """
        print(f"\n正在获取回复我的评论 (第 {page} 页)...")
        
        # 检查登录状态
        if not self.check_login_status():
            print("未登录，无法获取回复")
            return []
        
        # 准备通用请求头
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Referer": "https://message.bilibili.com/",
            "Origin": "https://message.bilibili.com",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive"
        }
        
        # 尝试使用多种API获取回复
        api_methods = [
            {
                "name": "消息中心API",
                "url": "https://api.bilibili.com/x/msgfeed/unread",
                "params": {
                    "build": 0,
                    "mobi_app": "web"
                },
                "api_type": "unread"
            },
            {
                "name": "回复消息API",
                "url": "https://api.bilibili.com/x/msgfeed/reply",
                "params": {
                "platform": "web",
                    "build": 0,
                    "mobi_app": "web",
                "ps": page_size,
                    "pn": page
                },
                "api_type": "msgfeed"
            },
            {
                "name": "会话API",
                "url": "https://api.vc.bilibili.com/session_svr/v1/session_svr/get_sessions",
                "params": {
                    "session_type": 1,  # 1表示回复我的
                    "group_fold": 1,
                    "unfollow_fold": 0,
                    "sort_rule": 2,
                    "build": 0,
                    "mobi_app": "web"
                },
                "api_type": "session"
            },
            {
                "name": "新版回复API",
                "url": "https://api.bilibili.com/x/v2/reply/reply/cursor",
                "params": {
                    "type": 17,  # 17表示回复我的
                "pn": page,
                    "ps": page_size
                },
                "api_type": "cursor"
            },
            {
                "name": "动态回复API",
                "url": "https://api.vc.bilibili.com/dynamic_svr/v1/dynamic_svr/dynamic_new",
                "params": {
                    "type_list": 268435455,
                    "from": "",
                    "platform": "web"
                },
                "api_type": "dynamic"
            },
            {
                "name": "私信API",
                "url": "https://api.vc.bilibili.com/web_im/v1/web_im/fetch_msg",
                "params": {
                    "sender_uid": 0,
                    "build": 0,
                    "mobi_app": "web"
                },
                "api_type": "private_msg"
            }
        ]
        
        all_replies = []
        
        # 尝试每种API方法
        for method in api_methods:
            try:
                print(f"\n尝试使用{method['name']}获取回复...")
                print(f"请求URL: {method['url']}")
                print(f"请求参数: {method['params']}")
                
                # 添加随机延迟，避免频繁请求
                time.sleep(random.uniform(0.5, 1.5))
                
                response = self.session.get(
                    method['url'], 
                    params=method['params'], 
                    headers=headers, 
                    timeout=15
                )
                
                print(f"响应状态码: {response.status_code}")
                
                if response.status_code == 200:
            data = response.json()
                    print(f"API返回码: {data.get('code')}")
                    
                    if data["code"] == 0 and "data" in data:
                        # 处理回复数据
                        replies = self._process_raw_replies(data["data"], method['api_type'])
                        
                        if replies:
                            print(f"成功通过{method['name']}获取到 {len(replies)} 条回复")
                            all_replies.extend(replies)
                            
                            # 如果已经获取到足够的回复，可以提前结束
                            if len(all_replies) >= page_size:
                                print(f"已获取足够的回复 ({len(all_replies)} 条)")
                                break
                else:
                            print(f"{method['name']}未返回有效回复")
            else:
                        print(f"API返回错误: {data.get('message', '未知错误')}")
                else:
                    print(f"请求失败，状态码: {response.status_code}")
            
        except Exception as e:
                print(f"使用{method['name']}获取回复时出错: {e}")
                continue
        
        # 如果以上方法都失败，尝试直接从网页获取
        if not all_replies:
            try:
                print("\n尝试直接从网页获取回复...")
                
                # 访问消息中心页面
                message_url = "https://message.bilibili.com/#/reply"
                response = self.session.get(message_url, headers=headers)
                
                if response.status_code == 200:
                    print("成功访问消息中心页面")
                    
                    # 尝试从网页源码中提取回复数据
                    try:
                        match = re.search(r'__INITIAL_STATE__\s*=\s*({.*?});', response.text)
                        if match:
                            state_data = json.loads(match.group(1))
                            if "reply" in state_data and "messages" in state_data["reply"]:
                                messages = state_data["reply"]["messages"]
                                print(f"从网页源码中提取到 {len(messages)} 条回复")
                                replies = self._process_raw_replies(messages, "web")
                                all_replies.extend(replies)
                    except Exception as e:
                        print(f"从网页源码中提取回复数据失败: {e}")
            except Exception as e:
                print(f"从网页获取回复时出错: {e}")
        
        # 去重处理
        if all_replies:
            unique_replies = []
            seen_rpids = set()
            
            for reply in all_replies:
                rpid = reply.get("rpid", 0)
                if rpid and rpid not in seen_rpids:
                    seen_rpids.add(rpid)
                    unique_replies.append(reply)
            
            print(f"\n成功获取 {len(unique_replies)} 条不重复回复")
            return unique_replies
        else:
            print("所有尝试都失败，无法获取回复")
            return []
    
    def _process_raw_replies(self, items, api_type):
        """
        处理原始回复数据
        
        Args:
            items: 原始回复数据列表或字典
            api_type: API类型，用于区分不同的数据结构
            
        Returns:
            处理后的回复列表
        """
        print(f"\n处理API类型 '{api_type}' 的回复数据...")
        
        if not items:
            print("回复数据为空")
            return []
            
        processed_replies = []
        
        # 保存原始数据，用于调试
        try:
            debug_filename = f"bilibili_raw_replies_{api_type}.json"
            print(f"保存原始回复数据到 {debug_filename}")
            with open(debug_filename, "w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存原始回复数据失败: {e}")
        
        # 首先检查items是否为字典类型，如果是，尝试提取实际的回复列表
        if isinstance(items, dict):
            print(f"items是字典类型，包含键: {list(items.keys())}")
            
            # 根据不同API类型处理数据结构
            if api_type == "unread":
                if "reply" in items:
                    items = items["reply"]
                    print(f"从unread API提取到reply字段，包含 {len(items) if isinstance(items, list) else '非列表'} 条数据")
            
            # 尝试从常见字段中提取回复列表
            for field in ["items", "replies", "list", "data", "messages", "reply_list", "reply"]:
                if field in items and items[field] is not None:
                    if isinstance(items[field], list):
                        items = items[field]
                        print(f"从字典中提取到 '{field}' 字段，包含 {len(items)} 条回复")
                        break
                    elif isinstance(items[field], dict):
                        # 如果字段值是字典，递归处理
                        return self._process_raw_replies(items[field], api_type)
            
            # 如果没有找到明确的列表字段，尝试其他方法
            if isinstance(items, dict):
                # 检查是否有特殊结构
                if "cursor" in items and "list" in items:
                    items = items["list"]
                    print(f"从cursor结构中提取到 {len(items)} 条回复")
                elif "cards" in items:
                    items = items["cards"]
                    print(f"从cards字段中提取到 {len(items)} 条回复")
                # 最后尝试使用所有值
                elif any(isinstance(v, list) for v in items.values()):
                    potential_lists = [v for v in items.values() if isinstance(v, list)]
                    # 选择最长的列表
                    items = max(potential_lists, key=len, default=[])
                    print(f"从字典值中提取到 {len(items)} 条回复")
                else:
                    # 如果找不到列表，将整个字典作为单个项处理
                    print("无法从字典中提取回复列表，将整个字典作为单个项处理")
                    items = [items]
        
        # 确保items是列表
        if not isinstance(items, list):
            print(f"items不是列表类型，而是 {type(items).__name__}，尝试转换")
            try:
                if isinstance(items, str):
                    items = json.loads(items)
                    if isinstance(items, list):
                        print(f"成功将字符串解析为列表，包含 {len(items)} 项")
                    else:
                        items = [items]
                else:
                    items = [items]
            except Exception as e:
                print(f"转换items为列表失败: {e}")
                items = [items]
        
        print(f"开始处理 {len(items)} 条原始回复数据")
        
        # 过滤和处理回复数据
        for item_index, item in enumerate(items):
            try:
                # 如果item不是字典，尝试解析为字典
                if not isinstance(item, dict):
                    try:
                        if isinstance(item, str):
                            item = json.loads(item)
                            if not isinstance(item, dict):
                                print(f"跳过非字典项 #{item_index}")
                                continue
                        else:
                            print(f"跳过非字典项 #{item_index}")
                            continue
        except Exception as e:
                        print(f"解析项 #{item_index} 失败: {e}")
                        continue
                
                # 跳过特殊的元数据字段
                if "cursor" == item.get("business_id") or "cursor" == item.get("id"):
                    print(f"跳过元数据项 #{item_index}")
                    continue
                
                # 跳过空项
                if not item:
                    print(f"跳过空项 #{item_index}")
                    continue
                
                # 打印当前项的键，帮助调试
                item_keys = list(item.keys())
                if len(item_keys) > 10:
                    print(f"处理项 #{item_index}，包含 {len(item_keys)} 个键")
                else:
                    print(f"处理项 #{item_index}，键: {item_keys}")
                
                # 构建回复对象
                reply = {}
                
                # 提取回复ID
                for id_field in ["rpid", "id", "id_str", "reply_id", "msg_id", "oid"]:
                    if id_field in item:
                        reply["rpid"] = item[id_field]
                        break
            else:
                    # 如果找不到明确的ID，使用索引作为临时ID
                    reply["rpid"] = item_index + int(time.time() * 1000)
                
                # 提取对象ID
                for oid_field in ["oid", "business_id", "subject_id", "target_id", "rid"]:
                    if oid_field in item:
                        reply["oid"] = item[oid_field]
                        break
                else:
                    # 如果找不到明确的对象ID，使用回复ID
                    reply["oid"] = reply["rpid"]
                
                # 提取评论类型
                for type_field in ["type", "business_type", "reply_type"]:
                    if type_field in item:
                        reply["type"] = item[type_field]
                        break
                else:
                    reply["type"] = 1  # 默认为视频评论
                
                # 提取用户信息
                reply["mid"] = 0
                reply["uname"] = "未知用户"
                
                # 从各种可能的用户信息字段中提取
                user_fields = ["user", "member", "sender", "author", "upper"]
                for user_field in user_fields:
                    if user_field in item and isinstance(item[user_field], dict):
                        user = item[user_field]
                        
                        # 提取用户ID
                        for mid_field in ["mid", "uid", "id", "userId"]:
                            if mid_field in user:
                                reply["mid"] = user[mid_field]
                                break
                        
                        # 提取用户名
                        for name_field in ["name", "uname", "nickname", "userName"]:
                            if name_field in user:
                                reply["uname"] = user[name_field]
                                break
                        
                        # 如果找到了用户信息，不再继续查找
                        if reply["mid"] and reply["uname"] != "未知用户":
                            break
                
                # 如果没有从用户对象中找到，尝试直接从item中提取
                if not reply["mid"]:
                    for mid_field in ["mid", "uid", "sender_uid", "author_id"]:
                        if mid_field in item:
                            reply["mid"] = item[mid_field]
                            break
                
                if reply["uname"] == "未知用户":
                    for name_field in ["uname", "name", "sender_uname", "author_name"]:
                        if name_field in item:
                            reply["uname"] = item[name_field]
                            break
                
                # 提取评论内容
                content = ""
                
                # 首先检查item中的直接内容字段
                for content_field in ["content", "message", "text", "title", "description", "reply_content"]:
                    if content_field in item:
                        content = item[content_field]
                        if content:  # 只有当内容不为空时才跳出循环
                            break
                
                # 如果没有找到直接内容，检查嵌套结构
                if not content:
                    nested_fields = ["item", "reply", "card", "desc"]
                    for nested_field in nested_fields:
                        if nested_field in item and isinstance(item[nested_field], dict):
                            nested = item[nested_field]
                            for content_field in ["content", "message", "text", "title", "description"]:
                                if content_field in nested:
                                    content = nested[content_field]
                                    if content:  # 只有当内容不为空时才跳出循环
                                        break
                            if content:  # 如果找到内容，跳出外层循环
                                break
                
                # 如果内容是字典类型，尝试提取实际内容
                if isinstance(content, dict):
                    for content_field in ["message", "content", "text"]:
                        if content_field in content:
                            content = content[content_field]
                            if isinstance(content, str):  # 确保提取的是字符串
                                break
                    
                    # 如果仍然是字典，转换为字符串
                    if isinstance(content, dict):
                        try:
                            content = json.dumps(content, ensure_ascii=False)
                        except:
                            content = str(content)
                
                # 确保内容是字符串
                if not isinstance(content, str):
                    content = str(content)
                
                reply["content"] = content
                
                # 提取评论时间
                for time_field in ["ctime", "timestamp", "time", "reply_time", "pubdate", "created_at"]:
                    if time_field in item:
                        reply["ctime"] = item[time_field]
                        break
            else:
                    reply["ctime"] = int(time.time())
                
                # 只有当内容不为空时才添加到处理结果中
                if reply["content"]:
                    processed_replies.append(reply)
                    print(f"成功处理回复 #{item_index}: {reply['rpid']} 来自 {reply['uname']}")
                else:
                    print(f"跳过空内容回复 #{item_index}")
                
        except Exception as e:
                print(f"处理回复数据 #{item_index} 异常: {e}")
                continue
        
        print(f"成功处理 {len(processed_replies)}/{len(items)} 条回复")
        
        # 如果没有处理成功任何回复，尝试直接使用原始数据
        if not processed_replies and items:
            print("未能处理任何回复，尝试直接构造简单回复对象...")
            
            # 尝试直接构造简单的回复对象
            for i, item in enumerate(items):
                try:
                    # 提取或构造内容
                    content = ""
                    if isinstance(item, dict):
                        # 尝试提取内容
                        for field in ["content", "message", "title", "description", "text"]:
                            if field in item:
                                content = item[field]
                                if content:
                                    break
                        
                        # 如果找不到内容，尝试转换整个对象为字符串
                        if not content:
                            try:
                                content = json.dumps(item, ensure_ascii=False)
                            except:
                                content = str(item)
                    elif isinstance(item, str):
                        content = item
                    else:
                        content = str(item)
                    
                    # 构造简单回复对象
                    reply = {
                        "rpid": i + 1,
                        "oid": 0,
                        "type": 1,
                        "mid": 0,
                        "uname": "未知用户",
                        "content": content,
                        "ctime": int(time.time())
                    }
                    
                    processed_replies.append(reply)
                    print(f"直接构造回复 #{i}")
        except Exception as e:
                    print(f"直接构造回复 #{i} 失败: {e}")
    
        return processed_replies
    
    def get_reply_info(self, reply):
        """
        从回复对象中提取信息
        
        Args:
            reply: 回复对象
            
        Returns:
            回复信息字典
        """
        try:
            # 处理不同类型的回复对象
            if isinstance(reply, str):
                # 如果是字符串，尝试解析JSON
                try:
                    reply_dict = json.loads(reply)
                    if isinstance(reply_dict, dict):
                        reply = reply_dict
                    else:
                        return {
                            "rpid": 0,
                            "oid": 0,
                            "type": 1,
                            "mid": 0,
                            "uname": "未知用户",
                            "content": reply,
                            "ctime": int(time.time())
                        }
                except:
                    # 如果无法解析为JSON，则作为纯文本内容处理
                    return {
                        "rpid": 0,
                        "oid": 0,
                        "type": 1,
                        "mid": 0,
                        "uname": "未知用户",
                        "content": reply,
                        "ctime": int(time.time())
                    }
            
            # 提取回复ID
            rpid = 0
            if "rpid" in reply:
                rpid = reply.get("rpid", 0)
            elif "id" in reply:
                rpid = reply.get("id", 0)
            elif "reply_id" in reply:
                rpid = reply.get("reply_id", 0)
            
            # 提取对象ID
            oid = 0
            if "oid" in reply:
                oid = reply.get("oid", 0)
            elif "business_id" in reply:
                oid = reply.get("business_id", 0)
            elif "subject_id" in reply:
                oid = reply.get("subject_id", 0)
            
            # 提取评论类型
            type_id = 1  # 默认为视频评论
            if "type" in reply:
                type_id = reply.get("type", 1)
            
            # 提取用户信息
            mid = 0
            uname = "未知用户"
            
            if "mid" in reply:
                mid = reply.get("mid", 0)
            elif "sender_uid" in reply:
                mid = reply.get("sender_uid", 0)
            
            if "member" in reply and isinstance(reply["member"], dict):
                member = reply["member"]
                if "uname" in member:
                    uname = member.get("uname", "未知用户")
                elif "name" in member:
                    uname = member.get("name", "未知用户")
            elif "user" in reply and isinstance(reply["user"], dict):
                user = reply["user"]
                if "uname" in user:
                    uname = user.get("uname", "未知用户")
                elif "name" in user:
                    uname = user.get("name", "未知用户")
            elif "uname" in reply:
                uname = reply.get("uname", "未知用户")
            
            # 提取评论内容
            content = ""
            if "content" in reply:
                if isinstance(reply["content"], dict) and "message" in reply["content"]:
                    content = reply["content"].get("message", "")
            else:
                    content = reply["content"]
            elif "message" in reply:
                content = reply.get("message", "")
            
            # 提取评论时间
            ctime = int(time.time())
            if "ctime" in reply:
                ctime = reply.get("ctime", ctime)
            elif "reply_time" in reply:
                ctime = reply.get("reply_time", ctime)
            
            return {
                "rpid": rpid,
                "oid": oid,
                "type": type_id,
                "mid": mid,
                "uname": uname,
                "content": content,
                "ctime": ctime
            }
        except Exception as e:
            print(f"提取回复信息时出错: {e}")
            # 返回一个默认的回复信息
            return {
                "rpid": 0,
                "oid": 0,
                "type": 1,
                "mid": 0,
                "uname": "未知用户",
                "content": str(reply) if reply else "",
                "ctime": int(time.time())
            }
    
    def get_video_comments(self, aid, page=1):
        """
        获取视频评论，支持多种API尝试和BV号转换
        
        Args:
            aid: 视频ID (av号或BV号)
            page: 页码
            
        Returns:
            评论列表
        """
        # 检查是否为BV号，如果是则尝试转换
        if isinstance(aid, str) and aid.startswith("BV"):
            print(f"检测到BV号: {aid}，尝试转换为av号...")
            try:
                # 直接从网页获取av号
                bv_url = f"https://www.bilibili.com/video/{aid}"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                    "Referer": "https://www.bilibili.com"
                }
                response = self.session.get(bv_url, headers=headers, timeout=10)
                if response.status_code == 200:
                    match = re.search(r'"aid":(\d+)', response.text)
                    if match:
                        aid = match.group(1)
                        print(f"成功将BV号转换为av号: {aid}")
                    else:
                        print(f"无法从网页提取av号")
            except Exception as e:
                print(f"BV号转换出错: {e}")
        
        # 首先使用备用API（已证明更有效）
        backup_url = "https://api.bilibili.com/x/v2/reply/main"
            params = {
            "type": 1,
                "oid": aid,
            "mode": 3,  # 按热度排序
                "next": page,
            "ps": 30
        }
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Referer": f"https://www.bilibili.com/video/av{aid}"
        }
        
        try:
            print(f"\n正在获取视频 av{aid} 的评论 (第 {page} 页)...")
            print(f"使用备用API: {backup_url}")
            print(f"请求参数: {params}")
            
            # 添加随机延迟，避免频繁请求
            time.sleep(random.uniform(1, 2))
            
            response = self.session.get(backup_url, params=params, headers=headers, timeout=15)
            print(f"备用API响应状态码: {response.status_code}")
            
            if response.status_code == 200:
            data = response.json()
                print(f"备用API返回码: {data.get('code')}")
            
            if data["code"] == 0:
                    if "data" in data and "replies" in data["data"]:
                        replies = data["data"]["replies"]
                        if replies:
                            print(f"成功获取到 {len(replies)} 条评论")
                            return replies
                        else:
                            print("评论列表为空，尝试其他API")
                    else:
                        print("返回数据结构异常，尝试其他API")
                else:
                    print(f"备用API返回错误: {data.get('message', '未知错误')}，尝试其他API")
            
            # 如果备用API失败，尝试原始API
            url = "https://api.bilibili.com/x/v2/reply"
            params = {
                "type": 1,
                "oid": aid,
                "pn": page,
                "ps": 30,  # 增加每页评论数
                "sort": 2  # 按热度排序
            }
            
            print("\n尝试使用原始API...")
            print(f"原始API URL: {url}")
            print(f"请求参数: {params}")
            
            # 添加随机延迟
            time.sleep(random.uniform(1, 2))
            
            response = self.session.get(url, params=params, headers=headers, timeout=15)
            print(f"原始API响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"原始API返回码: {data.get('code')}")
                
                if data["code"] == 0:
                    if "data" in data and "replies" in data["data"]:
                        replies = data["data"]["replies"]
                        if replies:
                            print(f"通过原始API成功获取到 {len(replies)} 条评论")
                            return replies
            else:
                            print("原始API评论列表为空")
                    else:
                        print("原始API返回数据结构异常")
                else:
                    print(f"原始API返回错误: {data.get('message', '未知错误')}")
            
            # 如果都失败了，尝试使用网页版API
            web_url = f"https://www.bilibili.com/video/av{aid}"
            print("\n尝试从网页版获取评论...")
            print(f"网页URL: {web_url}")
            
            # 添加随机延迟
            time.sleep(random.uniform(1, 2))
            
            response = self.session.get(web_url, headers=headers, timeout=15)
            print(f"网页版响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                # 从网页内容中提取评论API的参数
                try:
                    match = re.search(r'"aid":(\d+),"bvid":"([^"]+)"', response.text)
                    if match:
                        real_aid = match.group(1)
                        bvid = match.group(2)
                        print(f"从网页提取到 aid: {real_aid}, bvid: {bvid}")
                        
                        # 使用提取到的参数重新请求评论
                        comment_api = "https://api.bilibili.com/x/v2/reply/main"
                        params = {
                            "type": 1,
                            "oid": real_aid,
                            "mode": 3,
                            "next": page,
                            "ps": 30
                        }
                        
                        # 添加随机延迟
                        time.sleep(random.uniform(1, 2))
                        
                        response = self.session.get(comment_api, params=params, headers=headers, timeout=15)
                        print(f"评论API响应状态码: {response.status_code}")
                        
                        if response.status_code == 200:
                            data = response.json()
                            print(f"评论API返回码: {data.get('code')}")
                            
                            if data["code"] == 0:
                                if "data" in data and "replies" in data["data"]:
                                    replies = data["data"]["replies"]
                                    if replies:
                                        print(f"最终成功获取到 {len(replies)} 条评论")
                                        return replies
            else:
                                        print("最终评论列表为空")
                                else:
                                    print("最终返回数据结构异常")
                            else:
                                print(f"最终API返回错误: {data.get('message', '未知错误')}")
                    else:
                        print("无法从网页提取必要参数")
        except Exception as e:
                    print(f"解析网页数据时出错: {e}")
            
            # 最后尝试使用wbi接口
            try:
                print("\n尝试使用wbi接口...")
                wbi_url = "https://api.bilibili.com/x/v2/reply/wbi"
                wbi_params = {
                    "type": 1,
                    "oid": aid,
                    "pn": page,
                    "ps": 30,
                    "sort": 2
                }
                
                # 添加随机延迟
                time.sleep(random.uniform(1, 2))
                
                response = self.session.get(wbi_url, params=wbi_params, headers=headers, timeout=15)
                print(f"wbi接口响应状态码: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"wbi接口返回码: {data.get('code')}")
                    
                    if data["code"] == 0:
                        if "data" in data and "replies" in data["data"]:
                            replies = data["data"]["replies"]
                            if replies:
                                print(f"通过wbi接口成功获取到 {len(replies)} 条评论")
                                return replies
                            else:
                                print("wbi接口评论列表为空")
                        else:
                            print("wbi接口返回数据结构异常")
                    else:
                        print(f"wbi接口返回错误: {data.get('message', '未知错误')}")
            except Exception as e:
                print(f"wbi接口请求出错: {e}")
            
            print("所有尝试都失败，无法获取评论")
            return []
            
        except requests.exceptions.Timeout:
            print("请求超时")
            return []
        except requests.exceptions.RequestException as e:
            print(f"请求异常: {e}")
            return []
        except Exception as e:
            print(f"获取评论时出错: {e}")
            return []
    
    def analyze_comment_content(self, content):
        """
        分析评论内容，提取特征
        
        Args:
            content: 评论内容
            
        Returns:
            特征字典
        """
        # 初始化特征字典
        features = {
            'length': 0,                  # 评论长度
            'has_url': False,             # 是否包含URL
            'has_phone': False,           # 是否包含电话号码
            'has_email': False,           # 是否包含邮箱
            'has_qq': False,              # 是否包含QQ号
            'has_sensitive': False,       # 是否包含敏感词
            'has_emoji': False,           # 是否包含emoji
            'has_mention': False,         # 是否@他人
            'emotional_intensity': 0.0,   # 情感强度
            'pattern_matches': {},        # 匹配的模式
            'combined_categories': set(), # 组合的类别
            'keywords': []                # 匹配的关键词
        }
        
        if not content:
            return features
        
        # 计算评论长度
        features['length'] = len(content)
        
        # 检查是否包含URL
        if re.search(r'https?://\S+|www\.\S+', content):
            features['has_url'] = True
        
        # 检查是否包含电话号码
        if re.search(r'1[3-9]\d{9}', content):
            features['has_phone'] = True
        
        # 检查是否包含邮箱
        if re.search(r'\S+@\S+\.\S+', content):
            features['has_email'] = True
        
        # 检查是否包含QQ号
        if re.search(r'[qQ][qQ][:：]?\s*\d{5,11}', content):
            features['has_qq'] = True
        
        # 检查是否@他人
        if re.search(r'@[\w\u4e00-\u9fa5]+', content):
            features['has_mention'] = True
        
        # 检查是否包含emoji
        if re.search(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F700-\U0001F77F\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\U00002702-\U000027B0\U000024C2-\U0001F251]+', content):
            features['has_emoji'] = True
        
        # 分析情感强度
        features['emotional_intensity'] = self._analyze_emotional_intensity(content)
        
        # 检查极端华为粉评论模式
        huawei_patterns = {
            '品牌崇拜': [
                r'华为[是最好的|第一|无敌|领先全球|领先美国|比苹果强|秒杀苹果|秒杀三星]',
                r'[除了|只有]华为[没有别的选择|其他都是垃圾]',
                r'华为[就是|就像|就好比][国家|民族|中国]的骄傲',
                r'支持华为[就是|就等于]支持中国',
                r'华为[手机|技术|芯片|系统][世界第一|全球领先|无人能敌|傲视群雄]'
            ],
            '技术夸大': [
                r'华为[5G|6G|AI|芯片|操作系统|鸿蒙][领先|遥遥领先|领先全球|世界第一|美国落后|已经超越|甩开|秒杀]',
                r'华为[已经|早就|迅速|全面][突破|解决|掌握|不受限制]',
                r'华为[不需要|根本不用|完全不靠|早就不用][美国|高通|安卓|谷歌|苹果|三星|外国]的[技术|芯片|系统]',
                r'[鸿蒙|方舟|昇腾|麒麟][超越|领先|打败|碾压][安卓|iOS|高通|苹果|谷歌|Windows]',
                r'华为[自研|自主研发|独立研发|完全自主][芯片|系统|软件|算法|技术][超越|领先|打败][美国|苹果|谷歌|高通]'
            ],
            '阴谋论': [
                r'[美国|西方|外国][打压|封锁|制裁|恐惧|害怕|嫉妒]华为',
                r'华为[崛起|成功|发展|技术|实力][让|使得|导致][美国|西方|外国][坐不住|睡不着|恐慌|害怕]',
                r'[美国|苹果|谷歌|微软|三星|外国公司][偷|窃取|抄袭|复制|模仿]华为[技术|创新|设计|功能]',
                r'[美国|西方][不择手段|使绊子|泼脏水|造谣|污蔑|妖魔化]华为',
                r'华为[被禁|被封|被制裁]是因为[太强大|威胁到|挑战了][美国|西方|霸权]'
            ],
            '爱国营销': [
                r'[爱国|中国人|国人][就要|必须|应该|只能|才会]支持[华为|国产|中国品牌]',
                r'[不买|不用|不支持]华为[就是|等于|算是][不爱国|汉奸|卖国贼|崇洋媚外|美分|精日]',
                r'[买|用|支持][苹果|三星|外国品牌][就是|等于|算是][不爱国|汉奸|卖国贼|崇洋媚外|美分|精日]',
                r'[用华为|支持华为|买华为]是[爱国|最基本的爱国|爱国行为|爱国表现]',
                r'[华为|国产][情怀|信仰|骄傲|自豪感]'
            ],
            '人身攻击': [
                r'[不支持|不买|不用|质疑|批评]华为的[都是|肯定是|必然是|只能是][美分|汉奸|卖国贼|恨国党|精日|崇洋媚外|洋奴|美狗|日杂]',
                r'[用苹果|用三星|用外国手机]的[都是|肯定是|必然是|只能是][美分|汉奸|卖国贼|恨国党|精日|崇洋媚外|洋奴|美狗|日杂]',
                r'[理性|客观|中立]评价华为的[都是|肯定是|必然是|只能是][美分|汉奸|卖国贼|恨国党|精日|崇洋媚外|洋奴|美狗|日杂]',
                r'[不爱国|恨国|反华|精日|美分|汉奸|卖国贼][滚出中国|滚出去|死全家|该死]',
                r'[质疑|批评|不买|不用]华为的[该死|去死|滚|活该|死全家]'
            ]
        }
        
        # 检查是否匹配极端华为粉模式
        for category, patterns in huawei_patterns.items():
            matches = []
            for pattern in patterns:
                if re.search(pattern, content):
                    matches.append(pattern)
            
                if matches:
                features['pattern_matches'][category] = matches
                features['combined_categories'].add(category)
        
        # 分析情感特征
        
        # 检查极端情绪词
        extreme_emotions = [
            '气炸了', '笑死了', '气死了', '恶心死了', '烦死了', '厉害了', '牛逼了',
            '太恶心', '太可怕', '太讽刺', '太搞笑', '太愚蠢', '太无知', '太可悲',
            '绝对是', '必然是', '肯定是', '一定是', '只能是', '毫无疑问是',
            '永远不会', '永远都是', '永远支持', '永远反对', '永远热爱', '永远憎恨'
        ]
        
        for word in extreme_emotions:
            if word in content:
                features['keywords'].append(word)
        
        # 检查极端立场词
        extreme_stance = [
            '死忠粉', '脑残粉', '铁粉', '毒粉', '真爱粉', '黑粉', '喷子', '键盘侠',
            '洗地', '洗白', '抹黑', '带节奏', '引战', '挑事', '杠精', '撕逼',
            '跪舔', '舔狗', '舔', '吹', '吹捧', '吹嘘', '膜拜', '崇拜'
        ]
        
        for word in extreme_stance:
            if word in content:
                features['keywords'].append(word)
        
        # 检查攻击性词汇
        attack_words = [
            '垃圾', '废物', '傻逼', '智障', '脑残', '白痴', '蠢货', '猪脑子',
            '狗屁', '放屁', '屁话', '放狗屁', '狗屎', '废话', '胡说八道',
            '滚', '滚蛋', '滚开', '滚出去', '死', '去死', '该死', '死全家',
            '操', '日', '艹', '草', '妈的', '你妈', '尼玛', '特么', '他妈'
        ]
        
        for word in attack_words:
            if word in content:
                features['keywords'].append(word)
        
        # 检查极端对比词
        comparison_words = [
            '完爆', '秒杀', '碾压', '吊打', '甩开', '甩几条街', '甩十条街',
            '吊着打', '完虐', '虐爆', '爆锤', '暴打', '血虐', '血洗',
            '降维打击', '降维攻击', '降维碾压', '降维秒杀'
        ]
        
        for word in comparison_words:
            if word in content:
                features['keywords'].append(word)
        
        # 检查极端程度词
        degree_words = [
            '绝对', '必然', '肯定', '一定', '毫无疑问', '毫无悬念', '毫无例外',
            '永远', '永远不会', '永远都是', '永远支持', '永远反对',
            '彻底', '完全', '全面', '全部', '统统', '所有', '一切',
            '最', '最强', '最好', '最差', '最垃圾', '最优秀', '最先进'
        ]
        
        for word in degree_words:
            if word in content:
                features['keywords'].append(word)
        
        return features
    
    def is_malicious_comment(self, comment_text):
        """
        判断评论是否为恶意评论，增强对华为极端粉丝言论的识别，同时避免误判
        
        Args:
            comment_text: 评论内容
            
        Returns:
            bool: 是否为恶意评论
        """
        if not comment_text or not isinstance(comment_text, str):
            return False
            
        # 1. 首先检查是否包含直接的极端攻击性词汇
        direct_keywords = {
            # 品牌攻击
            "米猴": "brand_attack",
            "米蛆": "brand_attack",
            "果蛆": "brand_attack",
            "三蛆": "brand_attack",
            "越南厂": "brand_attack",
            "高通垃圾": "brand_attack",
            "联发科垃圾": "brand_attack",
            "苹果垃圾": "brand_attack",
            "小米垃圾": "brand_attack",
            "三星垃圾": "brand_attack",
            "谷歌垃圾": "brand_attack",
            "安卓垃圾": "brand_attack",
            "iOS垃圾": "brand_attack",
            "鸿蒙天下第一": "brand_attack",
            
            # 歧视性言论
            "洋垃圾": "discrimination",
            "美帝良心": "discrimination",
            "美帝走狗": "discrimination",
            "美帝工具": "discrimination",
            "美帝帮凶": "discrimination",
            "日本狗": "discrimination",
            "韩国狗": "discrimination",
            "台巴子": "discrimination",
            "台毒": "discrimination",
            "港毒": "discrimination",
            "精日": "discrimination",
            "精美": "discrimination",
            "恨国党": "discrimination",
            "公知": "discrimination",
            
            # 极端对立
            "卖国贼": "extreme_opposition",
            "汉奸": "extreme_opposition",
            "走狗": "extreme_opposition",
            "叛徒": "extreme_opposition",
            "美分": "extreme_opposition",
            "五毛": "extreme_opposition",
            "粉红": "extreme_opposition",
            "战狼": "extreme_opposition",
            "小粉红": "extreme_opposition",
            "反贼": "extreme_opposition",
            "精美": "extreme_opposition",
            
            # 水军特征
            "带节奏": "army_terms",
            "洗地": "army_terms",
            "五毛": "army_terms",
            "水军": "army_terms",
            "网评员": "army_terms",
            "公关": "army_terms",
            "洗白": "army_terms",
            "引战": "army_terms",
            
            # 人身攻击
            "脑残": "personal_attack",
            "智障": "personal_attack",
            "傻逼": "personal_attack",
            "废物": "personal_attack",
            "垃圾": "personal_attack",
            "狗东西": "personal_attack",
            "滚蛋": "personal_attack",
            "去死": "personal_attack",
            "有病": "personal_attack",
            "神经病": "personal_attack",
            "白痴": "personal_attack",
            "蠢货": "personal_attack",
            "猪脑子": "personal_attack",
            
            # 政治敏感
            "共产党": "political",
            "民主": "political",
            "自由": "political",
            "独裁": "political",
            "专制": "political",
            "言论自由": "political",
            "新闻自由": "political",
            "人权": "political",
            "政治正确": "political",
            "政治敏感": "political",
            "反华": "political",
            "辱华": "political"
        }
        
        # 检查直接关键词
        detected_direct = []
        for keyword, category in direct_keywords.items():
            if keyword in comment_text:
                detected_direct.append((keyword, category))
        
        # 如果直接检测到极端攻击词，直接判定为恶意评论
        if detected_direct:
            keywords_str = "，".join(f"{k}({c})" for k, c in detected_direct)
            print(f"检测到极端攻击词: {keywords_str}")
            return True
        
        # 2. 检查华为相关上下文
        huawei_keywords = ["华为", "麒麟", "海思", "鸿蒙", "方舟", "备胎", "自研", "自主", "余承东", "任正非"]
        is_huawei_context = any(word in comment_text for word in huawei_keywords)
        
        # 3. 分析需要上下文判断的关键词
        context_keywords = {
            # 攻击性词汇
            "垃圾": 3,
            "傻逼": 5,
            "脑残": 5,
            "智障": 5,
            "滚": 3,
            "滚蛋": 4,
            "滚开": 4,
            "有病": 3,
            "神经病": 4,
            "白痴": 4,
            "蠢": 2,
            "废物": 4,
            
            # 极端情绪
            "恨": 2,
            "气死": 2,
            "气炸": 2,
            "气疯": 2,
            "愤怒": 2,
            "怒了": 2,
            "恶心": 3,
            "吐了": 2,
            
            # 极端表达
            "最差": 2,
            "最烂": 3,
            "最垃圾": 4,
            "无敌": 2,
            "天下第一": 3,
            "吊打": 3,
            "碾压": 3,
            "秒杀": 3,
            "领先": 1,
            "领先十年": 4,
            "领先全球": 4,
            "领先世界": 4,
            
            # 民族主义
            "爱国": 2,
            "卖国": 5,
            "汉奸": 5,
            "民族": 1,
            "国产": 1,
            "国货": 1,
            "中国制造": 1,
            "中国骄傲": 3,
            "民族骄傲": 3,
            "民族品牌": 2,
            
            # 阴谋论
            "打压": 2,
            "封锁": 2,
            "制裁": 2,
            "遏制": 2,
            "围剿": 3,
            "阴谋": 4,
            "阳谋": 4,
            "霸权": 3,
            "霸凌": 3
        }
        
        # 计算上下文关键词得分
        context_score = 0
        detected_context = []
        
        for keyword, weight in context_keywords.items():
            if keyword in comment_text:
                context_score += weight
                detected_context.append((keyword, weight))
        
        # 4. 检查特定模式
        patterns = [
            # 极端对立模式
            (r"(华为|中国|国产).*?好.*?(苹果|三星|小米|谷歌|安卓|外国).*?不行", "极端对立"),
            (r"(苹果|三星|小米|谷歌|安卓|外国).*?不行.*?(华为|中国|国产).*?好", "极端对立"),
            (r"支持(华为|国产).*?抵制(苹果|三星|小米|谷歌|安卓|外国)", "极端对立"),
            (r"用(苹果|三星|小米|谷歌|安卓).*?就是.*?(卖国|崇洋媚外|汉奸)", "极端对立"),
            
            # 极端夸大模式
            (r"华为.*?领先.*?(\d+年|全球|世界|美国|苹果|三星)", "极端夸大"),
            (r"(麒麟|海思|鸿蒙).*?领先.*?(\d+年|全球|世界)", "极端夸大"),
            (r"华为.*?(吊打|碾压|秒杀).*?(苹果|三星|小米|谷歌)", "极端夸大"),
            (r"(麒麟|海思|鸿蒙).*?(吊打|碾压|秒杀).*?(高通|苹果|安卓)", "极端夸大"),
            
            # 极端民族主义
            (r"华为.*?(民族脊梁|民族之光|国产之光|中国之光)", "极端民族主义"),
            (r"支持华为.*?就是支持.*?中国", "极端民族主义"),
            (r"不用华为.*?就是.*?(卖国|汉奸)", "极端民族主义"),
            
            # 人身攻击
            (r"你.*?(脑残|智障|傻逼|废物|垃圾|滚|有病|白痴)", "人身攻击"),
            (r"(脑残|智障|傻逼|废物|垃圾|有病|白痴).*?的(人|家伙|东西)", "人身攻击"),
            
            # 阴谋论
            (r"美国.*?(打压|制裁|封锁).*?华为", "阴谋论"),
            (r"(西方|美帝).*?(打压|制裁|封锁).*?(中国|华为)", "阴谋论"),
            (r"华为.*?(被|遭到).*?(打压|制裁|封锁)", "阴谋论")
        ]
        
        # 检查模式匹配
        detected_patterns = []
        for pattern, label in patterns:
            if re.search(pattern, comment_text, re.IGNORECASE):
                detected_patterns.append((pattern, label))
                context_score += 3  # 模式匹配额外加分
        
        # 5. 综合判断
        # 基础阈值
        threshold = 5
        
        # 如果是华为相关上下文，适当降低阈值
        if is_huawei_context:
            threshold = 4
        
        # 输出调试信息
        if detected_context:
            context_keywords_str = "，".join(f"{k}({w})" for k, w in detected_context)
            print(f"检测到上下文关键词: {context_keywords_str}")
        
        if detected_patterns:
            patterns_str = "，".join(label for _, label in detected_patterns)
            print(f"检测到模式: {patterns_str}")
        
        print(f"上下文得分: {context_score}，阈值: {threshold}")
        
        # 返回最终判断结果
        return context_score >= threshold
        
    def auto_report_malicious_comments(self, keyword, video_count=5, comment_pages=2, reason_type=None):
        """
        自动搜索视频并举报恶意评论
        
        Args:
            keyword: 搜索关键词
            video_count: 检查的视频数量
            comment_pages: 每个视频检查的评论页数
            reason_type: 举报类型ID，如果为None则自动判断
            
        Returns:
            统计信息
        """
        print(f"\n开始搜索包含关键词 '{keyword}' 的视频并举报恶意评论...")
        
        # 检查登录状态
        if not self.check_login_status():
            print("未登录，无法执行操作")
            return None
        
        # 统计信息
        stats = {
            "processed_videos": 0,
            "processed_comments": 0,
            "malicious_comments": 0,
            "reported_comments": 0,
            "extreme_huawei_comments": 0,
            "extreme_types_count": {}  # 记录各种极端类型的数量
        }
        
        # 搜索视频
        videos = self.search_videos(keyword, page=1, page_size=video_count)
        
        if not videos or len(videos) == 0:
            print(f"未找到包含关键词 '{keyword}' 的视频")
            return stats
        
        print(f"找到 {len(videos)} 个视频，开始检查评论...")
        
        # 处理每个视频
        for video_index, video in enumerate(videos[:video_count]):
            aid = video.get("aid")
            title = video.get("title", "未知标题")
            author = video.get("author", "未知作者")
            
            print(f"\n正在处理第 {video_index+1}/{min(video_count, len(videos))} 个视频:")
            print(f"标题: {title}")
            print(f"作者: {author}")
            print(f"AID: {aid}")
            
            if not aid:
                print("无效的视频ID，跳过")
                continue
            
            stats["processed_videos"] += 1
            
            try:
                # 获取视频评论
                all_comments = []
            
            # 获取多页评论
            for page in range(1, comment_pages + 1):
                    comments = self.get_video_comments(aid, page)
                if not comments:
                    print(f"视频 av{aid} 第 {page} 页没有评论")
                        break
                        
                    all_comments.extend(comments)
                    print(f"已获取 {len(all_comments)} 条评论")
                    
                    # 页面之间添加随机延迟
                    if page < comment_pages:
                        delay = random.uniform(2, 5)
                        print(f"等待 {delay:.1f} 秒后获取下一页...")
                        time.sleep(delay)
                
                if not all_comments:
                    print(f"视频 av{aid} 没有评论")
                    continue
                
                print(f"共获取到 {len(all_comments)} 条评论")
                
                # 处理每条评论
                for comment_index, comment in enumerate(all_comments):
                    try:
                        print(f"\n处理第 {comment_index+1}/{len(all_comments)} 条评论")
                        
                        # 提取评论内容，处理可能的不同格式
                        content = ""
                        if isinstance(comment, dict):
                            if "content" in comment:
                                if isinstance(comment["content"], dict):
                                    content = comment["content"].get("message", "")
                                else:
                                    content = comment["content"]
                            elif "message" in comment:
                                content = comment["message"]
                        else:
                            content = str(comment)
                            
                        rpid = comment.get("rpid", 0)
                        
                        if not content or not rpid:
                            print("评论内容或ID为空，跳过")
                        continue
                    
                        stats["processed_comments"] += 1
                        
                        # 打印评论内容摘要
                        content_preview = content[:50] + "..." if len(content) > 50 else content
                        print(f"评论内容: {content_preview}")
                        
                        # 检查是否为恶意评论
                        is_malicious = self.is_malicious_comment(content)
                        
                        # 检查是否为华为极端粉丝评论
                        is_huawei_fanatic, huawei_reasons = self._is_huawei_fanatic_comment(content)
                        
                        # 确定极端类型
                        extreme_types = []
                        if is_malicious or is_huawei_fanatic:
                            extreme_types = self._determine_extreme_types(content)
                            
                            # 更新统计信息
                        for extreme_type in extreme_types:
                                if extreme_type in stats["extreme_types_count"]:
                                    stats["extreme_types_count"][extreme_type] += 1
                                else:
                                    stats["extreme_types_count"][extreme_type] = 1
                        
                        # 处理检测结果
                        if is_malicious:
                            print(f"检测到恶意评论")
                            stats["malicious_comments"] += 1
                            
                            if is_huawei_fanatic:
                                print(f"检测到极端华为粉评论，原因: {', '.join(huawei_reasons)}")
                                stats["extreme_huawei_comments"] += 1
                                
                            if extreme_types:
                                print(f"检测到的极端类型: {', '.join(extreme_types)}")
                            
                            # 确定举报类型
                            current_reason_type = reason_type
                            if current_reason_type is None:
                                # 自动判断举报类型
                                determined_reason_type = self._determine_report_reason_type(content, extreme_types)
                                reasons = self.get_report_reasons()
                                
                                if determined_reason_type in reasons:
                                    print(f"自动判断举报类型: {reasons[determined_reason_type]}")
                                    current_reason_type = determined_reason_type
                                else:
                                    print("无法自动判断举报类型，使用默认类型")
                                    current_reason_type = 4  # 默认使用人身攻击
                            
                            # 生成举报详情
                            detail = self._generate_report_detail(content, current_reason_type, extreme_types)
                            
                            # 举报评论
                            if self.report_comment(aid, rpid, current_reason_type, detail):
                                stats["reported_comments"] += 1
                                print(f"成功举报评论 {rpid}")
                            else:
                                print(f"举报评论 {rpid} 失败")
                        else:
                            print(f"评论内容正常，无需举报")
                        
                        # 评论之间添加随机延迟，避免频率限制
                        if comment_index < len(all_comments) - 1:
                            delay = random.uniform(1, 3)
                            print(f"等待 {delay:.1f} 秒后处理下一条评论...")
                time.sleep(delay)
        
                    except Exception as e:
                        print(f"处理评论时出错: {e}")
                        continue
                    
                # 视频之间添加较长延迟
                if video_index < min(video_count, len(videos)) - 1:
                    delay = random.uniform(5, 10)
                    print(f"\n等待 {delay:.1f} 秒后处理下一个视频...")
                    time.sleep(delay)
                        
            except Exception as e:
                print(f"处理视频 {aid} 时出错: {e}")
                continue
        
        # 打印统计信息
        print("\n检查完成，统计信息:")
        print(f"处理视频数: {stats['processed_videos']}/{video_count}")
        print(f"处理评论数: {stats['processed_comments']}")
        print(f"恶意评论数: {stats['malicious_comments']}")
        print(f"极端华为粉评论数: {stats['extreme_huawei_comments']}")
        print(f"成功举报数: {stats['reported_comments']}")
        
        # 打印各种极端类型的统计
        if stats["extreme_types_count"]:
            print("\n极端类型统计:")
            for extreme_type, count in sorted(stats["extreme_types_count"].items(), key=lambda x: x[1], reverse=True):
                print(f"{extreme_type}: {count}条")
        
        return stats
    
    def auto_report_replies_to_me(self, page_count=5, reason_type=None, detect_huawei_fans=True):
        """
        自动检测并举报恶意回复，包括华为极端粉丝攻击小米车祸的言论
        
        Args:
            page_count: 获取的页数
            reason_type: 举报理由类型ID，None表示自动判断
            detect_huawei_fans: 是否检测华为极端粉丝言论
            
        Returns:
            处理统计信息
        """
        print(f"开始获取回复我的评论并检测恶意回复 (页数: {page_count})...")
        
        # 初始化统计信息
        stats = {
            "total_pages": 0,
            "total_replies": 0,
            "processed_replies": 0,
            "malicious_replies": 0,
            "extreme_huawei_replies": 0,
            "xiaomi_car_attack_replies": 0,  # 新增小米汽车攻击计数
            "reported_replies": 0,
            "extreme_types_count": {},
            "report_types_count": {}
        }
        
        # 获取所有回复
        all_replies = []
        for api_type in ["main", "curReply"]:
            for page in range(1, page_count + 1):
                try:
                    # 获取评论
                    replies = self.get_replies_to_me(page=page, api_type=api_type)
                    
                    if replies and len(replies) > 0:
                        all_replies.extend(replies)
                        stats["total_pages"] += 1
                        print(f"从 {api_type} API 获取第 {page} 页回复, 获取到 {len(replies)} 条")
                    else:
                        print(f"从 {api_type} API 获取第 {page} 页回复, 没有回复或无法获取")
                        break
                        
                except Exception as e:
                    print(f"获取回复时出错: {e}")
                    continue
                    
                # 防止请求过快
                time.sleep(random.uniform(1, 2))
        
        # 统计回复总数
        stats["total_replies"] = len(all_replies)
        print(f"共获取到 {stats['total_replies']} 条回复")
        
        # 如果没有回复，直接返回
        if not all_replies:
            print("没有获取到回复，退出")
            return stats
        
        # 处理每条回复
        for reply_index, reply in enumerate(all_replies):
            try:
                # 提取回复信息
                reply_info = self.get_reply_info(reply)
                
                rpid = reply_info.get("rpid", 0)
                oid = reply_info.get("oid", 0)
                type_id = reply_info.get("type", 1)
                content = reply_info.get("content", "")
                uname = reply_info.get("uname", "未知用户")
                mid = reply_info.get("mid", 0)
                
                print(f"\n处理回复 {rpid} 来自 {uname}(UID:{mid}):")
                
                # 打印回复内容摘要
                content_preview = content[:50] + "..." if len(content) > 50 else content
                print(f"内容: {content_preview}")
                
                if not content or not rpid:
                    print("回复内容或ID为空，跳过")
                    continue
                
                stats["processed_replies"] += 1
                
                # 检查是否为恶意评论 (基础规则检测)
                is_malicious = self.is_malicious_comment(content)
                
                # 检查是否为华为极端粉丝评论
                is_huawei_fanatic = False
                huawei_reasons = None
                xiaomi_car_extreme = False
                car_extreme_result = None
                
                # 初始化毒性检测结果
                toxicity_results = None
                
                # 检查车祸相关关键词
                car_accident_keywords = ["车祸", "事故", "撞", "死亡", "113", "绿化带", "水泥墩", "落锁", "开门", 
                                       "激光雷达", "提前2秒", "每秒30米", "问界出事", "小米出事"]
                
                has_car_accident_keywords = any(keyword in content for keyword in car_accident_keywords)
                
                if detect_huawei_fans:
                    # 检查是否为华为极端粉丝评论
                    is_huawei_fanatic, huawei_reasons = self._is_huawei_fanatic_comment(content)
                    
                    # 检查是否为针对小米汽车的极端言论
                    if hasattr(self.fanatic_detector, 'detect_xiaomi_car_extremism'):
                        xiaomi_car_extreme, car_extreme_result = self.fanatic_detector.detect_xiaomi_car_extremism(content)
                    
                    # 使用Detoxify模型进行预测
                    if hasattr(self.fanatic_detector, '_predict_toxicity'):
                        try:
                            toxicity_results = self.fanatic_detector._predict_toxicity(content)
                            
                            # 如果是车祸相关评论但尚未被判定为极端，使用增强检测
                            if has_car_accident_keywords and not xiaomi_car_extreme and toxicity_results:
                                huawei_fan_score = toxicity_results.get("huawei_fan_score", 0)
                                
                                # 如果华为粉丝得分超过0.4，认为是极端言论
                                if huawei_fan_score > 0.4:
                                    xiaomi_car_extreme = True
                                    car_extreme_result = {
                                        "score": huawei_fan_score,
                                        "reason": f"Detoxify检测到与车祸相关的极端言论，华为粉丝得分: {huawei_fan_score:.2f}"
                                    }
                                    print(f"通过Detoxify增强检测识别出小米车祸极端言论")
                        except Exception as e:
                            print(f"毒性检测出错: {e}")
                
                # 确定极端类型
                extreme_types = []
                if is_malicious or is_huawei_fanatic or xiaomi_car_extreme:
                    extreme_types = self._determine_extreme_types(content)
                    
                    # 如果是车祸相关极端言论，增加特定标签
                    if xiaomi_car_extreme and "小米车祸攻击" not in extreme_types:
                        extreme_types.append("小米车祸攻击")
                    
                    # 更新统计信息
                    for extreme_type in extreme_types:
                        if extreme_type in stats["extreme_types_count"]:
                            stats["extreme_types_count"][extreme_type] += 1
                        else:
                            stats["extreme_types_count"][extreme_type] = 1
                
                # 处理检测结果
                report_reason = "未指定"
                if is_malicious or is_huawei_fanatic or xiaomi_car_extreme:
                    if is_malicious:
                        print(f"检测到恶意评论")
                        stats["malicious_replies"] += 1
                    
                    if is_huawei_fanatic:
                        print(f"检测到极端华为粉评论，原因: {huawei_reasons}")
                        stats["extreme_huawei_replies"] += 1
                        
                    if xiaomi_car_extreme and car_extreme_result:
                        car_score = car_extreme_result.get("score", 0)
                        car_reason = car_extreme_result.get("reason", "")
                        print(f"检测到小米汽车极端言论，得分: {car_score:.2f}，原因: {car_reason}")
                        stats["xiaomi_car_attack_replies"] += 1  # 使用新增的计数器
                        
                    if extreme_types:
                        print(f"检测到的极端类型: {', '.join(extreme_types)}")
                    
                    # 确定举报类型
                    current_reason_type = reason_type
                    if current_reason_type is None:
                        # 自动判断举报类型
                        determined_reason_type = self._determine_report_reason_type(content, extreme_types)
                        
                        # 小米车祸极端言论优先使用引战类型举报
                        if xiaomi_car_extreme or "小米车祸攻击" in extreme_types:
                            determined_reason_type = 7  # 引战
                        
                        reasons = self.get_comment_report_reasons()
                        
                        if determined_reason_type in reasons:
                            report_reason = reasons[determined_reason_type]
                            print(f"自动判断举报类型: {report_reason}")
                            current_reason_type = determined_reason_type
                        else:
                            print("无法自动判断举报类型，使用默认类型")
                            current_reason_type = 4  # 默认使用人身攻击
                            report_reason = "人身攻击"
                    else:
                        reasons = self.get_comment_report_reasons()
                        if current_reason_type in reasons:
                            report_reason = reasons[current_reason_type]
                    
                    # 更新举报类型统计
                    if report_reason in stats["report_types_count"]:
                        stats["report_types_count"][report_reason] += 1
                    else:
                        stats["report_types_count"][report_reason] = 1
                    
                    # 生成举报详情
                    detail = self._generate_report_detail(content, current_reason_type, extreme_types)
                    
                    # 小米车祸相关极端言论检测到的情况下增强举报理由
                    if xiaomi_car_extreme and car_extreme_result:
                        # 针对小米车祸言论，使用引战类型举报
                        if current_reason_type != 7:
                            current_reason_type = 7  # 引战
                            report_reason = "引战"
                            print(f"检测到车祸相关极端言论，调整举报类型为: 引战")
                        
                        # 增强举报详情
                        car_reason = car_extreme_result.get("reason", "")
                        if car_reason:
                            # 优化举报详情文本
                            detail = f"针对小米车祸事件的极端言论。{car_reason}该言论煽动用户对立，有意引发品牌争端，破坏平台环境。包含不当幸灾乐祸内容，违反社区规范。"
                    
                    # 使用毒性检测结果增强举报理由
                    if toxicity_results and toxicity_results.get("is_toxic", False):
                        toxic_index = toxicity_results.get("toxicity_index", 0)
                        huawei_fan_score = toxicity_results.get("huawei_fan_score", 0)
                        toxic_cats = toxicity_results.get("toxic_categories", [])
                        
                        print(f"Detoxify毒性指数: {toxic_index:.2f}，华为粉丝得分: {huawei_fan_score:.2f}")
                        print(f"毒性类别: {', '.join(toxic_cats)}")
                        
                        # 高毒性言论强化举报理由
                        if toxic_index > 0.5 or huawei_fan_score > 0.4:  # 降低阈值
                            # 提升举报详情的有效性
                            if "小米车祸攻击" in toxic_cats or car_extreme_result:
                                detail = f"针对小米车祸的极端言论，毒性指数{toxic_index:.2f}，包含明显的攻击、煽动和幸灾乐祸内容。该言论破坏社区氛围，制造品牌对立，属于典型的引战行为。"
                            else:
                                detail += f" 毒性指数较高({toxic_index:.2f})，包含{', '.join(toxic_cats)}等有害内容。"
                    
                    # 举报评论
                    for retry in range(3):  # 尝试最多3次
                        report_success = self.report_comment(oid, rpid, current_reason_type, detail, type_id)
                        if report_success:
                            stats["reported_replies"] += 1
                            print(f"成功举报评论 {rpid} (原因: {report_reason})")
                            break
                        else:
                            print(f"举报评论 {rpid} 失败，尝试第 {retry+1} 次")
                            time.sleep(random.uniform(1.5, 3.0))  # 失败后稍等一会再尝试
                else:
                    print(f"评论内容正常，无需举报")
            except Exception as e:
                print(f"处理回复 {reply_index} 时出错: {e}")
                traceback.print_exc()
                continue
            
            # 随机延时，防止请求过快
            time.sleep(random.uniform(0.5, 1.5))
        
        # 打印统计信息
        print("\n处理完成，统计信息:")
        print(f"总页数: {stats['total_pages']}")
        print(f"总回复数: {stats['total_replies']}")
        print(f"处理回复数: {stats['processed_replies']}")
        print(f"恶意回复数: {stats['malicious_replies']}")
        print(f"华为极端粉回复数: {stats['extreme_huawei_replies']}")
        print(f"小米汽车攻击回复数: {stats['xiaomi_car_attack_replies']}")
        print(f"成功举报数: {stats['reported_replies']}")
        
        if stats["extreme_types_count"]:
            print("\n极端类型统计:")
            for type_name, count in stats["extreme_types_count"].items():
                print(f"{type_name}: {count}")
        
        if stats["report_types_count"]:
            print("\n举报类型统计:")
            for reason, count in stats["report_types_count"].items():
                print(f"{reason}: {count}")
        
        return stats


def main():
    # 创建B站自动化实例
    bilibili = BilibiliAuto()
    
    # 检查登录状态
    if not bilibili.check_login_status():
        print("请检查cookie是否有效")
        return
    
    print("\n请选择要执行的操作：")
    print("1. 搜索视频并点赞/评论")
    print("2. 搜索视频并举报")
    print("3. 搜索视频并举报恶意评论")
    print("4. 检查'回复我的'并举报恶意评论")
    
    operation = input("请输入选项(1-4): ")
    
    if operation == "1":
        # 点赞/评论功能
        keyword = input("请输入要搜索的关键词: ")
        count = input("请输入要点赞的视频数量(默认5个): ")
        
        try:
            count = int(count) if count.strip() else 5
        except ValueError:
            count = 5
        
        # 询问是否需要评论
        need_comment = input("是否需要评论视频？(y/n): ").lower() == 'y'
        comment = None
        
        if need_comment:
            comment_type = input("选择评论方式：1.固定评论 2.随机评论: ")
            
            if comment_type == "1":
                comment = input("请输入评论内容: ")
            elif comment_type == "2":
                comments = []
                print("请输入多个评论内容，每行一个，输入空行结束:")
                while True:
                    line = input()
                    if not line:
                        break
                    comments.append(line)
                
                if comments:
                    comment = comments
                else:
                    print("未输入任何评论，将不进行评论")
        
        # 执行自动点赞和评论
        bilibili.auto_like_videos(keyword, count, comment)
    
    elif operation == "2":
        # 举报功能
        keyword = input("请输入要搜索的关键词: ")
        count = input("请输入要举报的视频数量(默认5个): ")
        
        try:
            count = int(count) if count.strip() else 5
        except ValueError:
            count = 5
        
        # 显示举报原因列表
        reasons = bilibili.get_report_reasons()
        print("\n举报原因列表：")
        for reason_id, reason_desc in reasons.items():
            print(f"{reason_id}. {reason_desc}")
        
        # 获取举报原因
        reason_type = input("请选择举报原因(1-10): ")
        try:
            reason_type = int(reason_type)
            if reason_type not in reasons:
                print("无效的举报原因，将使用'其他'原因")
                reason_type = 10
        except ValueError:
            print("无效的举报原因，将使用'其他'原因")
            reason_type = 10
        
        # 获取详细说明
        detail = input("请输入详细说明(可选): ")
        
        # 确认举报
        confirm = input(f"\n您将举报包含关键词 '{keyword}' 的 {count} 个视频，原因是 '{reasons[reason_type]}'。确认操作？(y/n): ")
        if confirm.lower() != 'y':
            print("操作已取消")
            return
        
        # 执行自动举报
        bilibili.auto_report_videos(keyword, count, reason_type, detail)
    
    elif operation == "3":
        # 评论举报功能
        keyword = input("请输入要搜索的关键词: ")
        video_count = input("请输入要检查的视频数量(默认5个): ")
        
        try:
            video_count = int(video_count) if video_count.strip() else 5
        except ValueError:
            video_count = 5
        
        comment_pages = input("请输入每个视频要检查的评论页数(默认2页): ")
        
        try:
            comment_pages = int(comment_pages) if comment_pages.strip() else 2
        except ValueError:
            comment_pages = 2
        
        # 显示评论举报原因列表
        reasons = bilibili.get_comment_report_reasons()
        print("\n评论举报原因列表：")
        for reason_id, reason_desc in reasons.items():
            print(f"{reason_id}. {reason_desc}")
        print("0. 自动判断举报类型")
        
        # 获取举报原因
        reason_type = input("请选择举报原因(默认0-自动判断): ")
        try:
            reason_type = int(reason_type) if reason_type.strip() else 0
            if reason_type not in reasons and reason_type != 0:
                print("无效的举报原因，将使用'自动判断'")
                reason_type = 0
        except ValueError:
            print("无效的举报原因，将使用'自动判断'")
            reason_type = 0
        
        # 确认操作
        if reason_type == 0:
            confirm = input(f"\n您将检查包含关键词 '{keyword}' 的 {video_count} 个视频的评论，并自动判断举报类型。确认操作？(y/n): ")
        else:
            reason_desc = reasons.get(reason_type, "未知")
            confirm = input(f"\n您将检查包含关键词 '{keyword}' 的 {video_count} 个视频的评论，并使用'{reason_desc}'原因举报恶意评论。确认操作？(y/n): ")
        
        if confirm.lower() != 'y':
            print("操作已取消")
            return
        
        # 执行自动评论举报
        if reason_type == 0:
            bilibili.auto_report_malicious_comments(keyword, video_count, comment_pages, None)  # 传入None表示自动判断
        else:
        bilibili.auto_report_malicious_comments(keyword, video_count, comment_pages, reason_type)
    
    elif operation == "4":
        # 回复举报功能
        page_count = input("请输入要检查的'回复我的'页数(默认5页): ")
        
        try:
            page_count = int(page_count) if page_count.strip() else 5
        except ValueError:
            page_count = 5
        
        # 显示评论举报原因列表
        reasons = bilibili.get_comment_report_reasons()
        print("\n评论举报原因列表：")
        for reason_id, reason_desc in reasons.items():
            print(f"{reason_id}. {reason_desc}")
        print("0. 自动判断举报类型")
        
        # 获取举报原因
        reason_type = input("请选择举报原因(默认0-自动判断): ")
        try:
            reason_type = int(reason_type) if reason_type.strip() else 0
            if reason_type not in reasons and reason_type != 0:
                print("无效的举报原因，将使用'自动判断'")
                reason_type = 0
        except ValueError:
            print("无效的举报原因，将使用'自动判断'")
            reason_type = 0
        
        # 确认操作
        if reason_type == 0:
            confirm = input(f"\n您将检查'回复我的'消息中的 {page_count} 页回复，并自动判断举报类型。确认操作？(y/n): ")
        else:
            reason_desc = reasons.get(reason_type, "未知")
            confirm = input(f"\n您将检查'回复我的'消息中的 {page_count} 页回复，并使用'{reason_desc}'原因举报恶意回复。确认操作？(y/n): ")
            
        if confirm.lower() != 'y':
            print("操作已取消")
            return
        
        # 执行自动回复举报
        if reason_type == 0:
            bilibili.auto_report_replies_to_me(page_count, None)  # 传入None表示自动判断
        else:
        bilibili.auto_report_replies_to_me(page_count, reason_type)
    
    else:
        print("无效的选项")


if __name__ == "__main__":
    main() 