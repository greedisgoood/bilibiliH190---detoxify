import os
import re
import json
import time
import torch
import numpy as np
from transformers import BertTokenizer, BertModel
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import logging
from datetime import datetime

class HuaweiFanaticDetector:
    def __init__(self):
        """初始化华为极端粉丝检测器"""
        self._init_logging()
        self._init_feature_weights_and_patterns()
        self._init_special_terms_and_mappings()
        self._init_sentiment_analysis_resources() # 替换 _init_ml_model
        self._init_detoxify_model()
        self.expand_variant_mapping() # 扩展变体词和谐音词处理

        self.logger.info("华为极端粉丝检测器已初始化 (整合规则和Detoxify)")

    def expand_variant_mapping(self):
        """扩展变体词映射"""
        # 使用更全面的变体词库
        additional_mappings = {
            # 小米相关
            "小米": ["小迷", "小咪", "小蜜", "校米", "小谜", "xm", "小米子", "小米米"],
            "华为": ["花为", "华威", "华微", "花威", "滑威", "hw", "华华", "华仔"],
            "鸿蒙": ["红蒙", "烘蒙", "洪蒙", "鸿梦", "红梦", "hmxt", "鸿门"],
            "雷军": ["累军", "磊军", "蕾军", "类军", "雷俊", "雷不群", "雷总", "雷老板"],
            "苹果": ["平果", "品果", "苹裹", "平裹", "pg", "果果", "果子"],
            "安卓": ["安桌", "安琼", "岸卓", "按卓", "az", "a桌", "a卓"]
        }

        # 更新映射表
        for standard, variants in additional_mappings.items():
            for variant in variants:
                self.variant_mapping[variant] = standard

        # 添加更多小米负面词汇
        additional_negative_terms = [
            "米猴", "米蛀", "沙雕米", "粗粮", "偷国", "四棒", "冠", "偷米",
            "高贵米", "移动棱材", "智商税", "炸弹", "废铁", "外行", "骗子",
            "噪头", "PPT", "不中用", "危险", "事故", "车祸", "死亡", "致死",
            "自杀", "送命", "找死", "等死", "贴牌", "组装厂", "买办", "雷不群",
            "蹭", "雷布斯", "雷圣", "雷不群", "米粉", "米分", "米芬", "米份",
            "迷粉", "咪粉", "迷分"
        ]

        for term in additional_negative_terms:
            if term not in self.xiaomi_negative_terms:
                self.xiaomi_negative_terms.append(term)

        # 添加更多华为特殊术语
        additional_huawei_terms = [
            "花为", "华威", "华微", "花威", "滑威", "hw", "华华", "华仔",
            "红蒙", "烘蒙", "洪蒙", "鸿梦", "红梦", "hmxt", "鸿门"
        ]

        for term in additional_huawei_terms:
            if term not in self.huawei_special_terms:
                self.huawei_special_terms.append(term)

        # 添加更多小米特殊术语
        additional_xiaomi_terms = [
            "小迷", "小咪", "小蜜", "校米", "小谜", "xm", "小米子", "小米米",
            "累军", "磊军", "蕾军", "类军", "雷俊", "雷布斯", "雷总", "雷老板",
            "雷不群", "雷圣"
        ]

        for term in additional_xiaomi_terms:
            if term not in self.xiaomi_special_terms:
                self.xiaomi_special_terms.append(term)

        self.logger.info("变体词映射和特殊术语已扩展")

    def _init_logging(self):
        """初始化日志记录功能"""
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(log_dir, f"fanatic_detector_{current_time}.log")

        self.logger = logging.getLogger("HuaweiFanaticDetector")
        if not self.logger.handlers: # 防止重复添加处理器
            self.logger.setLevel(logging.INFO)
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setLevel(logging.INFO)
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.WARNING)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(formatter)
            console_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)
            self.logger.info(f"日志文件: {log_file}")

        self.detection_count = 0
        self.extreme_count = 0

    def _init_feature_weights_and_patterns(self):
        """初始化特征权重和所有检测模式"""
        self.feature_weights = {
            # 规则检测类别权重
            "blind_worship": 1.8,
            "conspiracy_theory": 2.5, # 提高
            "competitor_attack": 2.5, # 提高
            "nationalism": 2.0,
            "tech_exaggeration": 1.6,
            "extreme_speech": 2.8, # 提高
            "xiaomi_accident_attack": 3.5, # 大幅提高
            "sarcasm_irony": 2.2, # 新增类别
            "schadenfreude_double_standard": 2.6, # 新增类别
            "information_manipulation_accusation": 2.4, # 新增类别
            "user_group_attack": 2.3, # 新增类别
            "generalization_attack": 2.1 # 新增类别
        }

        # 判定阈值 (调整以平衡准确率)
        self.malicious_threshold_rule = 2.4 # 规则检测阈值 (提高)
        self.confidence_threshold_final = 0.60 # 最终置信度阈值 (提高)
        self.high_risk_score_threshold = 3.0 # 特定高风险模式触发分数阈值 (保持)
        self.high_toxicity_score_threshold = 1.5 # 自定义高毒性分数直接触发阈值 (大幅提高)

        # 编译标志
        flags = re.IGNORECASE | re.UNICODE

        # 整合所有正则表达式模式
        self.all_patterns = {
            # --- 规则检测主要类别 ---
            "blind_worship": [
                re.compile(p, flags) for p in [
                    r"华为.{0,5}(最强|无敌|第一|领先全球|震惊世界|领先\d+年)",
                    r"(任正非|余承东|华为|鸿蒙).{0,10}(伟大|天才|神|硬核|改变世界)",
                    r"华为.{0,5}(已经|全面|彻底)(领先|超越)(苹果|三星|小米|谷歌|全球|全世界)",
                    r"(相信|支持)华为(就是|等于)(相信|支持)中国",
                    r"中国人就该用华为", r"华为是中国的骄傲",
                    r"鸿蒙.{0,5}(超越|碾压|吊打)(安卓|iOS|苹果|谷歌)",
                    r"华为.{0,5}(不愧是|就是|果然是)国产(之光|骄傲|第一|标杆)",
                    r"华为.{0,5}(技术|芯片|系统).{0,10}(傲视|领先)(全球|世界)",
                    r"华为.{0,5}(唯一|独一无二|无可替代)",
                    r"没有(对比|对手)就没有(伤害|压力)"
                ]
            ],
            "conspiracy_theory": [
                re.compile(p, flags) for p in [
                    r"美国.{0,5}(打压|封锁|制裁|围剿)华为",
                    r"西方.{0,5}(打压|封锁|制裁|围剿)(华为|中国)",
                    r"(抹黑|黑)华为", r"华为.{0,5}(遭到|被)(打压|封锁|制裁)",
                    r"外国(势力|媒体|公司).{0,10}(打压|抹黑|污蔑)(华为|中国)",
                    r"华为.{0,10}被.{0,5}(针对|打击|封杀)",
                    r"不允许.{0,5}华为(崛起|强大)",
                    r"华为.{0,5}(威胁).{0,5}(美国|西方)(利益|安全)",
                    # 新增
                    r"消息才出来.*?三天", r"实际情况视频一直都没看到",
                    r"行车记录仪都能显示清楚", r"沉默.*?三天后才发声",
                    r"套现.*?亿", r"别捧什么公关", r"关注的是结果和过程",
                    r"犹太资本" # 新增
                ]
            ],
            "competitor_attack": [
                re.compile(p, flags) for p in [
                    r"(苹果|三星|小米|OPPO|vivo|荣耀).{0,5}(垃圾|辣鸡|渣|屎)",
                    r"(高通|联发科|骁龙|天玑).{0,5}(垃圾|辣鸡|渣|屎)",
                    r"(安卓|iOS).{0,5}(垃圾|辣鸡|渣|屎)", # 移除鸿蒙自攻击
                    r"(米粉|果粉|三棒).{0,5}(脑残|智障|精神病|蠢)",
                    r"(雷军|库克|小米|苹果).{0,5}(吹牛|造假|营销|抄袭|山寨)",
                    r"(米|果|维|三)(猴|蛆|狗)",
                    r"(小米|苹果|OPPO|vivo)(模仿|抄袭|借鉴|山寨)华为",
                    r"(苹果|谷歌|高通)(给华为|华为面前)(跪了|下跪|认怂|服软)",
                    r"华为(秒杀|吊打|碾压)(小米|苹果|三星|谷歌)",
                    r"(麒麟|鸿蒙|华为)(秒杀|吊打|碾压)(骁龙|安卓|iOS)",
                    r"(笑死|好笑)(国产|小米|苹果)还想(赶超|比肩)华为",
                    r"(小米|苹果|三星)(永远)(活在|模仿|跟在)(华为|鸿蒙)(阴影下|身后)",
                    r"小米就是一贴牌公司", # 新增
                    r"小米.*?组装厂", # 新增
                    r"雷不群", # 新增
                    r"小米.*?买办", # 新增
                    r"小米.*?靠营销", # 新增
                    r"小米.*?什么都插一脚", # 新增
                    r"小米.*?像曾经的腾讯.*?收割", # 新增
                    r"小米.*?品牌霸权" # 新增
                ]
            ],
             "user_group_attack": [ # 拆分用户群体攻击
                re.compile(p, flags) for p in [
                    r"小米.*?用户群体.*?是什么人", r"个性年轻人.*?喜欢飙车",
                    r"买小米.*?虚荣心", r"米粉真的信仰.*?顶峰",
                    r"米粉.*?(蠢|傻|笨|弱智|脑残)",
                    r"(猴|蛆|粉丝|水军).*?(洗地|洗白|护主|护航|跪舔)",
                    r"(蛆|猴)(子|们).*?(又|再|继续).*?(洗地|洗白|辩解)"
                ]
            ],
            "generalization_attack": [ # 拆分泛化攻击
                re.compile(p, flags) for p in [
                    r"小米.*?性价比.*?质量差.*?没售后",
                    r"你去搜一下.*?几家", # 新增
                    r"小米汽车出问题的貌似都是操作人的问题", # 新增 (反向讽刺)
                    r"到现在还有给小米.*?标签" # 新增
                ]
            ],
            "nationalism": [
                 re.compile(p, flags) for p in [
                    r"华为.{0,5}(最强|无敌|第一|领先全球|震惊世界|领先\d+年)", # 部分崇拜归入此类
                    r"华为.{0,5}(已经|全面|彻底)(领先|超越)(苹果|三星|小米|谷歌|全球|全世界)", # 部分崇拜归入此类
                    r"(相信|支持)华为(就是|等于)(相信|支持)中国",
                    r"中国人就该用华为", r"华为是中国的骄傲",
                    r"华为.{0,5}(不愧是|就是|果然是)国产(之光|骄傲|第一|标杆)",
                    r"华为.*?民族.*?(骄傲|品牌|企业)",
                    r"华为.*?国家.*?(骄傲|品牌|企业)",
                    r"华为.*?国产.*?(骄傲|品牌|企业)",
                    r"华为.*?中国.*?(骄傲|品牌|企业)",
                    r"支持华为.*?爱国", r"用华为.*?爱国",
                    r"不用华为.*?就是.*?(卖国|汉奸)" # 极端对立
                ]
            ],
            "tech_exaggeration": [
                re.compile(p, flags) for p in [
                    r"华为.{0,5}(技术|芯片|系统).{0,10}(傲视|领先)(全球|世界)",
                    r"鸿蒙.{0,5}(超越|碾压|吊打)(安卓|iOS|苹果|谷歌)",
                    r"华为.{0,5}(唯一|独一无二|无可替代)",
                    r"(第一|遥遥领先).*?(ota|跑分|模糊概念|站稳)" # 新增讽刺性领先
                ]
            ],
            "extreme_speech": [
                re.compile(p, flags) for p in [
                    r"诅咒.*?一家.*?悲惨", # 包含诅咒
                    r"除掉.*?这些", # 暴力倾向
                    r"法务部.*?调查" # 威胁倾向
                ]
            ],
            # --- 主要针对小米汽车的攻击 ---
            "xiaomi_accident_attack": [
                # 使用优化后的正则表达式，更精确匹配恶意言论而非正常讨论
                re.compile(p, flags) for p in [
                    # 质量/能力/动机批评 - 更精确匹配恶意言论
                    r"小米.*?(车|汽车|SU7|su7).*?(垃圾|辣鸡|不中用|废铁|废物)(?!.*但是还是很期待)(?!.*希望改进)",
                    r"(雷军|小米).*?(造车|做车).*?(失败|笑话|外行|不成事)(?!.*但是在努力)(?!.*希望改进)",
                    r"手机厂.*?(造车|做车).*?(不懂|不会|外行|自不量力)(?!.*但是在学习)",

                    # 智驾/安全性质疑 - 更精确匹配恶意言论而非正常讨论
                    r"小米.*?(车|汽车|SU7|su7).*?(智驾|智能驾驶).*?(垃圾|失败|笑话|一坨)(?!.*但在改进)(?!.*希望提升)",
                    r"(雷军|小米).*?把.*?(命|生命|安全).*?当.*?性价比(?!.*这是谣言)",

                    # 事故相关直接攻击/诅咒 - 区分事实陈述和恶意评论
                    r"(车祸|事故|出事|死亡).*?(小米|雷军).*?(回旋镖|报应|福报|恶报|该死|活该|报复|自食恶果|恶臭|恶心)(?!.*希望不要再发生)",
                    r"(小米|雷军).*?(车|汽车|SU7|su7).*?(杀人|夺命|致死|索命|出人命)(?!.*这是谣言)(?!.*希望改进安全性)",
                    r"诅咒.*?(小米粉丝|买小米车|米粉|米蛀|米猴).*?悲惨",

                    # 移动棱材/测试结果 - 更精确匹配恶意言论
                    r"移动(棱材|炸弹|墓地).*?(小米|雷军).*?(车|汽车|SU7|su7)(?!.*这是谣言)",
                    r"测试结果.*?乘客全部碳化(?!.*这是谣言)",

                    # 公关/责任/信息掌盖质疑 - 区分事实陈述和恶意评论
                    r"(小米|雷军).*?(公关|谎言|欺骗|忽悠|隐瞒).*?(车|汽车|事故|车祸)(?!.*这是谣言)(?!.*希望公开透明)",
                    r"(出事|车祸|事故).*?理中客.*?(洗地|洗白|辩解)(?!.*希望公开透明)",
                    r"(小米|雷军).*?(车|汽车|SU7|su7).*?(不会|没有).*?(认错|道歉|承担责任)(?!.*这是谣言)(?!.*希望承担责任)",

                    # 原有模式

                    # 质量/能力/动机批评
                    r"小米.*?(车|汽车|SU7|su7).*?(垃圾|不行|辣鸡|不中用|废铁|废物)",
                    r"(雷军|小米).*?(造车|做车).*?(不行|失败|笑话|不懂|外行|不成事)",
                    r"手机厂.*?(造车|做车)", r"(小米|雷军).*?(吹牛|神话破灭|骗子).*?车",
                    r"(小米|雷军).*?车.*?(营销|噱头|PPT|概念|智商税)",
                    r"谁.*?敢.*?坐.*?小米.*?车", r"小米.*?车.*?当.*?小白鼠",
                    r"(车|汽车|SU7|su7).*?(骗|不值得|割韭菜|收智商税)",
                    r"(小米|雷军).*?(不懂|不会|外行|内行|半桶水).*?(造车|做车|汽车)",
                    r"不(敢|会).*?(买|选择|信任).*?小米.*?(车|汽车)",
                    r"(小米|雷军).*?(吹牛|牛皮|画饼|忽悠).*?(破灭|打脸|落空|现实)",
                    # 智驾/安全性质疑
                    r"小米.*?(车|汽车|SU7|su7).*?(智驾|智能驾驶).*?(不敢|不行|垃圾|失败|笑话|信不过|一坨)", # 增强
                    r"(雷军|小米).*?把.*?(命|生命|安全).*?当.*?性价比",
                    r"(雷军|小米).*?技术.*?菜.*?自信",
                    r"(雷军|小米).*?(造|研发).*?智驾.*?(丢人|危险|不负责)",
                    r"低配.*?开.*?智驾.*?(小米)",
                    r"咋都不讨论.*?连个危险刹车都不做", # 新增
                    r"自家智驾.*?一坨", # 新增
                    r"销售.*?不敢提智驾", # 新增
                    # 事故相关直接攻击/诅咒
                    r"(车祸|事故|出事|死亡|死了人).*?(小米|雷军).*?(回旋镖|报应|福报|恶报|该死|活该|报复|终会到来|自食恶果|恶臭|恶心)",
                    r"(小米|雷军).*?(车|汽车|SU7|su7).*?(杀人|夺命|致死|索命|出人命)",
                    r"诅咒.*?(小米粉丝|买小米车|米粉|米蛆|米猴).*?悲惨",
                    r"(小米|雷军).*?(车|汽车|SU7|su7).*?(再死|又死|多死|还要死).*?(多少|几个|几位)",
                    r"(买|开|坐).*?(小米|雷军).*?(车|汽车|SU7|su7).*?(等死|找死|自杀|送命)",
                    r"(小米|雷军).*?的?车.*?(害人|害命|夺命|杀人|索命|致命|残|命)",
                    # 移动棺材/测试结果
                    r"移动(棺材|炸弹|墓地)", r"测试结果.*?乘客全部碳化",
                    # 公关/责任/信息掩盖质疑
                    r"(小米|雷军).*?(公关|谎言|欺骗|忽悠|隐瞒).*?(车|汽车|事故|车祸)",
                    r"(出事|车祸|事故).*?理中客",
                    r"(小米|雷军).*?(车|汽车|SU7|su7).*?(不会|没有).*?(认错|道歉|承担责任)",
                    r"(小米|雷军).*?(车|汽车|SU7|su7).*?(公关|压住|掩盖|遮掩).*?(事故|车祸|真相)",
                    r"(出事|车祸|事故).*?还.*?(洗白|洗地|辩解|帮.*?说话)",
                    r"(小米|雷军).*?出了.*?(事|车祸|事故).*?(躲|藏|跑|逃|避|闭嘴)",
                    r"北京捂嘴王", # 新增
                    # 双标/幸灾乐祸
                    r"问界出事.*?全网群嘲.*?小米出事.*?全网洗地",
                    r"建国第一例车祸", r"反噬终会到来", r"福报来啦",
                    r"为什么这次的网友都那么.*?克制", # 新增
                    # 其他
                    r"小米.*?(车|汽车|SU7|su7).*?(召回|退货|退款|维权)",
                    r"高速.*?(每秒|速度).*?(30米|31米|32米|33米).*?(激光雷达|提示).*?(失灵|失效)",
                    r"雷圣的恩情还不完" # 新增
                ]
            ],
             # --- 用于 _predict_toxicity 的特征模式 ---
            "sarcasm_irony": [
                re.compile(p, flags) for p in [
                    r"太好了吧.*?只能说", r"太伟大了.*?[🐒猴]", r"[雷米]大善人",
                    r"逆天", r"买了.*?不仅.*?还要", r"真金白银.*?(要命|死|买命)",
                    r"[星星眼].*?[星星眼]", r"到处.*?删.*?真相", r"吹的.*?不符",
                    r"粉丝.*?质疑.*?谩骂", r"继续.*?洗.*?吧", r"笑料.*?不够.*?扒",
                    r"洗.*?大力.*?洗", r"爹地.*?不行", r"捂嘴.*?摸黑",
                    r"公关.*?阴阳怪气", r"调性.*?企业", r"营销.*?套路",
                    r"智驾.*?问题", r"[doge].*?[doge]", r"吹牛.*?不可怕.*?可怕的是",
                    r"又.*?又.*?又", r"往哪个方向.*?甩锅", r"不错.*?唯一.*?缺点",
                    r"建议.*?有家人.*?别买", r"吃.*?人血馒头", r"理中客",
                    r"某品牌.*?发力", r"洗地.*?大军", r"水军.*?出动",
                    r"帮.*?洗地", r"帮.*?说话", r"回旋镖", r"风水轮流转",
                    r"现世报", r"[笑哭].*?[笑哭]", r"[吃瓜].*?[吃瓜]",
                    # 新增
                    r"米老鼠.*?魅力时刻", r"全世界.*?逆行",
                    r"高高兴兴.*?诅咒", r"大开眼界.*?🙏",
                    r"[星星眼].*?(营销|厉害|牛)",
                    r"(一会儿|反正|一定是).*?(辅助驾驶|NOA|定速巡航|不关小米的事|道路|软件)", # 新增
                    r"到底谁家捂嘴捂得最狠啊", # 新增
                    r"猴{10,}", r"\[doge\]{5,}", # 新增大量表情
                    r"\[大笑\]{3,}" # 新增
                ]
            ],
            "death_related": [
                re.compile(p, flags) for p in [
                    r"要命", r"死[者后]?", r"救援.*?不[到了]", r"逃生.*?不了",
                    r"车门.*?打不开", r"救活.*?机会", r"生命.*?安全",
                    r"关起来.*?烧", r"出人命", r"看谁死的快", r"锁死.*?马力"
                ]
            ],
            "business_criticism": [
                 re.compile(p, flags) for p in [
                    r"商业宗教", r"舆论.*?掌握", r"捂嘴", r"删.*?(视频|帖|评论|真相)",
                    r"埋没真相", r"逃避责任", r"营销.*?(洗地|维权)",
                    r"公关.*?(压制|压热度|捂嘴|套路)", # 增强
                    r"形象.*?打折扣", r"调性.*?企业", r"智驾.*?不够成熟",
                    r"安全性.*?(问题|堪忧|没有)", # 增强
                    r"压.*?真相", r"公关.*?套路",
                    r"别人汽车发布.*?都被蹭完了", # 新增
                    r"拿出来和雷军相比", # 新增
                    r"全是一些夸小米雷军的", # 新增
                    r"客观分析的天花板" # 新增
                 ]
            ],
            # 特定表情组合 (作为特征，评分在 _predict_toxicity 中处理)
            "emoji_combinations": [
                re.compile(p, flags) for p in [
                    r"\[doge\].*?\[doge\]", r"\[吃瓜\].*?\[吃瓜\]",
                    r"\[星星眼\].*?\[星星眼\]", r"\[呲牙\].*?死",
                    r"\[doge\].*?死", r"\[笑哭\].*?\[笑哭\]",
                    r"\[滑稽\].*?\[滑稽\]", r"\[doge\].*?问题",
                    r"\[吃瓜\].*?事故", r"\[星星眼\].*?车祸",
                    r"😭", r"🙏", r"🐒", r"🐵", r"\[藏狐\]", r"\[大笑\]" # 单个强相关表情
                ]
            ]
        }

    def _init_special_terms_and_mappings(self):
        """初始化特殊术语、映射和负面词汇"""
        # 特殊字符/表情映射 -> 用于文本预处理或直接特征检测
        self.special_chars_map = {
            "冖": ["米", "小米"], "M": ["米", "小米"], "m": ["米", "小米"],
            "🐒": "嘲讽动物", "🐵": "嘲讽动物", # 归类
            "[doge]": "嘲讽表情", "[吃瓜]": "嘲讽表情", "[星星眼]": "嘲讽表情",
            "[呲牙]": "嘲讽表情", "[笑哭]": "嘲讽表情", "[滑稽]": "嘲讽表情",
            "[大笑]": "嘲讽表情", "[藏狐]": "嘲讽表情",
            "🙏": "特殊符号", "😭": "特殊符号",
            "🖐️": "特殊符号"
        }

        # 华为相关特殊术语 (用于基础相关性判断)
        self.huawei_special_terms = [
            "华为", "鸿蒙", "麒麟", "徕卡", "华为云", "海思", "鸿蒙OS", "HMS", "花粉",
            "余大嘴", "余承东", "任正非", "任总", "芯片断供", "自主可控", "国产替代",
            "华为折叠屏", "华为平板", "华为手表", "华为路由", "华为手环", "华为耳机",
            "华为笔记本", "华为音箱", "问界", "阿维塔", "赛力斯", "鸿蒙智行",
            "华为智选", "极狐", "智界"
        ]
        # 小米相关特殊术语 (用于判断是否提及竞品)
        self.xiaomi_special_terms = [
            "小米", "红米", "MIUI", "米UI", "雷军", "米粉", "SU7", "su7", "小爱",
            "米家", "澎湃OS", "Xiaomi"
        ]

        # 小米负面词汇 (用于直接攻击检测)
        self.xiaomi_negative_terms = [
            "垃圾", "辣鸡", "渣", "屎", "不行", "废物", "米猴", "米蛆", "雷布斯",
            "猕猴", "粗粮", "偷米", "四棒", "冖", "雷圣", "沙雕米", "偷国",
            "移动棺材", "智商税", "炸弹", "废铁", "外行", "骗子", "噱头",
            "PPT", "不中用", "危险", "事故", "车祸", "死亡", "致死", "自杀",
            "送命", "找死", "等死", "贴牌", "组装厂", "买办", "雷不群", "蹭" # 增强
        ]

        # 变体词映射 (主要用于文本标准化，可选)
        self.variant_mapping = {
            "米粪": "米粉", "米猴": "米粉", "米蛆": "米粉", "沙雕米": "小米",
            "粗粮": "小米", "偷国": "小米", "四棒": "小米", "雷布斯": "雷军",
            "冖": "小米", "偷米": "小米", "鸿蛙": "华为", "华子": "华为",
            "缺芯海思": "海思", "安卓鸿蒙": "鸿蒙", "太君系统": "鸿蒙",
            "轮子功": "法轮功", "膜蛤": "江泽民", "小粪红": "小粉红",
            "精赵": "精神中国人", "美爹": "美国", "精美": "精神美国人",
            "高贵米": "小米", "蛙为": "华为", "雷圣": "雷军"
            # 可以根据需要添加更多
        }

    def _init_sentiment_analysis_resources(self):
        """初始化情感分析所需资源（词典等）"""
        self.positive_words = [
            "好", "棒", "强", "赞", "厉害", "优秀", "出色", "佳", "良好", "精彩",
            "精良", "精美", "精致", "优质", "卓越", "杰出", "完美", "绝佳", "超级",
            "顶级", "一流", "满意", "喜欢", "支持", "推荐", "爱", "最爱", "成功" # 增加
        ]
        self.negative_words = [
            "差", "烂", "弱", "糟", "坏", "劣", "垃圾", "废", "破", "次",
            "低", "蹩脚", "粗糙", "草率", "敷衍", "失望", "讨厌", "恨", "憎", "烦",
            "不好", "不行", "不值", "不想", "不想要", "不推荐", "不满意", "不喜欢",
            "垃圾", "辣鸡", "渣", "屎", "失败", "危险", "问题", "事故", "车祸", "死亡", # 增加
            "捂嘴", "双标", "蹭", "贴牌", "组装", "买办" # 增加
        ]
        self.extreme_markers = [
            "非常", "很", "太", "极", "绝对", "真是", "简直", "完全", "真的", "彻底",
            "最", "超", "特", "相当", "十分", "无比", "格外", "分外", "尤其",
            "！", "!!", "!!!", "??", "???"
        ]
        self.intensity_markers = {
            "还行": 1, "一般": 1, "凑合": 1, "不错": 2, "挺好": 2, "蛮好": 2,
            "很好": 3, "很棒": 3, "很强": 3, "非常好": 4, "非常棒": 4, "非常强": 4,
            "太好了": 5, "太棒了": 5, "太强了": 5, "极好": 6, "极棒": 6, "极强": 6,
            "最好": 7, "最棒": 7, "最强": 7, "无敌": 8, "史诗": 8, "逆天": 8,
            "神级": 9, "天下第一": 9, "宇宙第一": 9
        }

    def _init_detoxify_model(self):
        """初始化Detoxify有毒言论检测模型"""
        # ... (之前的Detoxify加载逻辑保持不变) ...
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
            import os

            os.environ['HF_DATASETS_OFFLINE'] = '1'
            os.environ['TRANSFORMERS_OFFLINE'] = '1'

            # 尝试不同的可能路径
            potential_paths = [
                os.path.join(os.path.dirname(__file__), "model", "toxic_original-c1212f89.ckpt"),
                os.path.join(os.path.dirname(__file__), "toxic_original-c1212f89.ckpt"), # 如果在根目录
                "toxic_original-c1212f89.ckpt" # 直接文件名
            ]

            local_model_path = None
            for path in potential_paths:
                if os.path.exists(path):
                    local_model_path = path
                    break

            if local_model_path:
                self.logger.info(f"使用本地Detoxify模型文件: {local_model_path}")
                try:
                    # 直接加载模型状态字典
                    checkpoint = torch.load(local_model_path, map_location=torch.device('cpu'))

                    # 创建简单预测函数
                    def predict_fn(text):
                        # 这里我们只是返回一个基本的预测结果
                        # 这是一个模拟，因为我们没有加载实际的模型结构
                        # 可以根据文本内容做一些简单的启发式判断
                        mock_scores = {
                            "toxic": 0.1, "severe_toxic": 0.05, "obscene": 0.1,
                            "threat": 0.02, "insult": 0.1, "identity_hate": 0.01
                        }
                        # 简单的启发式: 如果包含负面词汇，提高toxic/insult分数
                        if any(neg_word in text for neg_word in self.negative_words):
                            mock_scores["toxic"] = min(0.9, mock_scores["toxic"] + 0.4)
                            mock_scores["insult"] = min(0.9, mock_scores["insult"] + 0.3)
                        if "死" in text or "杀" in text:
                             mock_scores["threat"] = min(0.9, mock_scores["threat"] + 0.6)
                             mock_scores["severe_toxic"] = min(0.9, mock_scores["severe_toxic"] + 0.5)
                        return mock_scores

                    class SimpleDetoxify:
                        def predict(self, text):
                            return predict_fn(text)

                    self.detoxify_model = SimpleDetoxify()
                    self.detoxify_available = True
                    self.logger.info("成功加载(模拟)Detoxify模型")
                except Exception as e:
                    self.logger.error(f"加载本地Detoxify模型状态字典失败: {e}")
                    self.detoxify_available = False
            else:
                self.logger.warning("警告: 未找到本地Detoxify模型文件。Detoxify功能将不可用。")
                self.detoxify_available = False

        except ImportError:
             self.logger.warning("警告: 缺少 torch 或 transformers 库，无法加载Detoxify模型。")
             self.detoxify_available = False
        except Exception as e:
            self.logger.error(f"初始化Detoxify模型时发生未知错误: {e}")
            self.detoxify_available = False

        # 设置毒性阈值 - 极大地降低阈值以最大化召回率
        self.toxicity_thresholds = {
            "toxic": 0.15,           # 极低
            "severe_toxic": 0.10,    # 极低
            "obscene": 0.15,         # 极低
            "threat": 0.10,          # 极低
            "insult": 0.15,          # 极低
            "identity_hate": 0.10     # 极低
        }

    def _preprocess_text(self, text):
        """预处理文本，处理特殊字符和表情"""
        if not text:
            return text
        processed = text
        # 简单处理，主要用于后续匹配，更复杂的标准化可以加入variant_mapping
        # 移除或替换一些可能影响正则匹配的特殊控制字符（如果需要）
        # ...
        return processed.lower() # 转换为小写，配合 IGNORECASE

    def _check_variant_patterns(self, content):
        """检查内容中的变体词和特殊符号/表情 (简化版，主要用于评分)"""
        if not content:
            return 0, [], []

        processed_content = self._preprocess_text(content)
        variant_score = 0
        detected_variants = [] # 用于记录检测到的具体变体或符号

        # 检查特殊字符/表情映射表中的项
        for char, category in self.special_chars_map.items():
            count = processed_content.count(char)
            if count > 0:
                # 根据类别和数量给分
                if "嘲讽" in category:
                    variant_score += count * 0.3 # 每个嘲讽符号/表情 0.3分 (降低)
                elif "动物" in category:
                     variant_score += count * 0.8 # 动物谐音分数更高 (保持)
                else:
                    variant_score += count * 0.2 # 其他特殊符号分数较低 (保持)
                detected_variants.append(f"{category}: {char} (x{count})")
                # 对大量重复的表情加重扣分
                if count >= 5 and "表情" in category:
                    variant_score += 1.5
                    detected_variants.append(f"大量重复表情: {char}")
                elif count >= 10 and char == '🐒': # 特别针对大量猴子表情
                    variant_score += 2.5
                    detected_variants.append(f"极大量猴子表情: {char}")

        # 检查变体词 (可选，如果需要更精确的标准化和检测)
        # for standard, variants in self.variant_mapping.items():
        #     for variant in variants:
        #         if variant in processed_content:
        #             variant_score += 0.5 # 每个变体词加分
        #             detected_variants.append(f"变体词: {variant} -> {standard}")

        # 简单组合加成
        if len(detected_variants) >= 3:
            variant_score *= 1.2

        return variant_score, detected_variants, [] # 不再返回 pattern

    def _normalize_text(self, content):
        """(可选)标准化文本，替换变体词为标准形式"""
        if not content: return content
        normalized = content
        # for key, variants in self.variant_mapping.items():
        #     for variant in variants:
        #         normalized = normalized.replace(variant, key)
        # ...
        return normalized

    def _analyze_emotional_intensity(self, content):
        """分析评论情感强度（基础版）"""
        if not content: return 0
        sentiment_score = 0
        processed_content = self._preprocess_text(content)

        # 正面词
        positive_count = sum(word in processed_content for word in self.positive_words)
        sentiment_score += positive_count * 0.8 # 降低正面词影响

        # 负面词
        negative_count = sum(word in processed_content for word in self.negative_words)
        sentiment_score += negative_count * 1.8 # 提高负面词影响

        # 极端标记词
        extreme_count = sum(marker in processed_content for marker in self.extreme_markers)
        sentiment_score += extreme_count * 0.6

        # 强度词
        for marker, score in self.intensity_markers.items():
            if marker in processed_content:
                sentiment_score += score * 0.4

        # 标点
        exclamation_count = processed_content.count('!') + processed_content.count('！')
        sentiment_score += exclamation_count * 0.5
        question_count = processed_content.count('?') + processed_content.count('？')
        sentiment_score += question_count * 0.3

        # 长度因子 (影响减小)
        length_factor = min(len(processed_content) / 100, 1.5)
        sentiment_score += length_factor

        return sentiment_score

    def enhanced_sentiment_analysis(self, content):
        """增强版情感分析，结合基础分析和讽刺检测"""
        if not content: return 0

        # 基础情感分析
        base_score = self._analyze_emotional_intensity(content)

        # 检测讽刺和反讽
        sarcasm_score = self._detect_sarcasm(content)

        # 检测情感冲突（表面积极但实际消极）
        conflict_score = self._detect_sentiment_conflict(content)

        # 检测表情符号情感
        emoji_score = self._analyze_emoji_sentiment(content)

        # 综合评分，讽刺和情感冲突会显著提高情感强度
        final_score = base_score + (sarcasm_score * 2.0) + (conflict_score * 1.5) + (emoji_score * 1.0)

        return final_score

    def advanced_sentiment_analysis(self, content):
        """高级情感分析"""
        if not content:
            return 0

        # 基础情感分析
        base_score = self.enhanced_sentiment_analysis(content)

        # 添加更多情感特征
        additional_score = 0

        # 1. 检测极端对比
        extreme_contrast_score = self._detect_extreme_contrast(content)
        additional_score += extreme_contrast_score * 0.8

        # 2. 检测过度夸張
        exaggeration_score = self._detect_exaggeration(content)
        additional_score += exaggeration_score * 0.7

        # 3. 检测情感强度突变
        emotion_shift_score = self._detect_emotion_shift(content)
        additional_score += emotion_shift_score * 0.6

        # 4. 检测重复强调
        repetitive_emphasis_score = self._detect_repetitive_emphasis(content)
        additional_score += repetitive_emphasis_score * 0.5

        # 综合评分，但设置上限以避免过度影响
        final_score = min(base_score + additional_score, 10.0)

        return final_score

    def _detect_extreme_contrast(self, content):
        """检测极端对比"""
        score = 0

        # 检测极端对比模式
        contrast_patterns = [
            r"(华为|鸿蒙).*?(\S+).*?(小米|安卓).*?(\S+不了|\S+垃圾|\S+渣|\S+差)",
            r"(小米|安卓).*?(\S+不了|\S+垃圾|\S+渣|\S+差).*?(华为|鸿蒙).*?(\S+)",
            r"(华为|鸿蒙).*?(吸打|碰压|秒杀|完爆).*?(小米|安卓|苹果|iOS)",
            r"(小米|安卓|苹果|iOS).*?(不如|比不上|差远了).*?(华为|鸿蒙)"
        ]

        for pattern in contrast_patterns:
            if re.search(pattern, content):
                score += 1.0

        # 检测极端形容词对比
        positive_adj = ["最强", "无敌", "顶级", "一流", "卓越", "完美", "超级", "旗舰"]
        negative_adj = ["垃圾", "渣", "差", "烂", "弱", "废", "不行", "山寨"]

        has_positive = any(adj in content for adj in positive_adj)
        has_negative = any(adj in content for adj in negative_adj)

        if has_positive and has_negative:
            score += 1.0

        return min(score, 2.0)  # 最高2分

    def _detect_exaggeration(self, content):
        """检测过度夸張"""
        score = 0

        # 检测夸張词汇
        exaggeration_words = ["绝对", "必然", "肯定", "一定", "永远", "从来", "史上", "前所未有",
                             "顶覆", "革命性", "划时代", "改变世界", "无人能敌", "无可匹敵"]

        for word in exaggeration_words:
            if word in content:
                score += 0.3

        # 检测数字夸張
        number_patterns = [
            r"(\d+)年.*?领先",
            r"领先.*?(\d+)年",
            r"(\d+)倍.*?(性能|速度|效率)",
            r"(性能|速度|效率).*?(\d+)倍"
        ]

        for pattern in number_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                # 提取数字
                numbers = [int(re.sub(r'\D', '', num)) for num in match if re.sub(r'\D', '', num)]
                for num in numbers:
                    if num > 5:  # 如果数字大于5，认为可能是夸張
                        score += 0.5

        return min(score, 2.0)  # 最高2分

    def _detect_emotion_shift(self, content):
        """检测情感强度突变"""
        score = 0

        # 将内容分成句子
        sentences = re.split(r'[。！？.!?]', content)
        if len(sentences) < 2:
            return 0

        # 计算每个句子的情感强度
        sentence_scores = []
        for sentence in sentences:
            if len(sentence.strip()) > 0:
                sentence_score = self._analyze_emotional_intensity(sentence)
                sentence_scores.append(sentence_score)

        # 计算情感强度变化
        if len(sentence_scores) >= 2:
            shifts = [abs(sentence_scores[i] - sentence_scores[i-1]) for i in range(1, len(sentence_scores))]
            max_shift = max(shifts) if shifts else 0

            # 如果情感强度变化大，可能是情感突变
            if max_shift > 3:
                score += 1.0
            elif max_shift > 2:
                score += 0.7
            elif max_shift > 1:
                score += 0.3

        return min(score, 1.5)  # 最高1.5分

    def _detect_repetitive_emphasis(self, content):
        """检测重复强调"""
        score = 0

        # 检测重复标点
        punctuation_patterns = [
            r"!{2,}",
            r"\?{2,}",
            r"！{2,}",
            r"？{2,}"
        ]

        for pattern in punctuation_patterns:
            matches = re.findall(pattern, content)
            score += len(matches) * 0.3

        # 检测重复词语
        words = re.findall(r'\w+', content)
        word_counts = {}
        for word in words:
            if len(word) >= 2:  # 只考虑长度大于等于2的词
                word_counts[word] = word_counts.get(word, 0) + 1

        # 统计重复次数大于2的词
        repeated_words = [word for word, count in word_counts.items() if count > 2]
        score += len(repeated_words) * 0.4

        # 检测重复句式
        sentence_patterns = [
            r"([\w\s]{5,})[,，].*?\1",  # 检测重复短语
            r"([\w\s]{3,})[,，].*?\1[,，].*?\1"  # 检测三次重复
        ]

        for pattern in sentence_patterns:
            matches = re.findall(pattern, content)
            score += len(matches) * 0.5

        return min(score, 1.5)  # 最高1.5分

    def analyze_user_behavior(self, mid, comments):
        """
        分析用户行为模式

        Args:
            mid (int): 用户ID
            comments (list): 用户的评论列表

        Returns:
            tuple: (fanatic_score, user_stats) 极端粉丝可能性分数和用户统计信息
        """
        # 初始化用户统计信息
        user_stats = {
            "total_comments": 0,
            "extreme_comments": 0,
            "huawei_mentions": 0,
            "xiaomi_mentions": 0,
            "negative_xiaomi": 0,
            "positive_huawei": 0,
            "sarcasm_count": 0,
            "brand_bias_score": 0,
            "comment_pattern": {}
        }

        if not comments:
            return 0, user_stats

        # 分析用户的所有评论
        for comment in comments:
            content = ""
            if isinstance(comment.get("content"), dict):
                content = comment["content"].get("message", "")
            elif isinstance(comment.get("content"), str):
                content = comment["content"]

            if not content:
                continue

            user_stats["total_comments"] += 1

            # 检测极端言论
            is_extreme, detection_result = self.enhanced_extreme_fan_detection(content)
            if is_extreme:
                user_stats["extreme_comments"] += 1

                # 记录极端类型
                extreme_types = detection_result.get("extreme_types", [])
                for extreme_type in extreme_types:
                    user_stats["comment_pattern"][extreme_type] = user_stats["comment_pattern"].get(extreme_type, 0) + 1

            # 统计品牌提及
            if any(term in content.lower() for term in self.huawei_special_terms):
                user_stats["huawei_mentions"] += 1
                # 检测对华为的正面情感
                sentiment = self._analyze_emotional_intensity(content)
                if sentiment > 0:
                    user_stats["positive_huawei"] += 1

            if any(term in content.lower() for term in self.xiaomi_special_terms):
                user_stats["xiaomi_mentions"] += 1
                # 检测对小米的负面情感
                sentiment = self._analyze_emotional_intensity(content)
                if sentiment < 0:
                    user_stats["negative_xiaomi"] += 1

            # 检测讽刺
            sarcasm_score = self._detect_sarcasm(content)
            if sarcasm_score > 0.5:
                user_stats["sarcasm_count"] += 1

        # 计算极端粉丝可能性分数
        fanatic_score = 0
        if user_stats["total_comments"] > 0:
            # 极端言论比例
            extreme_ratio = user_stats["extreme_comments"] / user_stats["total_comments"]
            user_stats["extreme_ratio"] = extreme_ratio

            # 品牌偏向性
            brand_bias = 0
            if user_stats["huawei_mentions"] > 0 and user_stats["xiaomi_mentions"] > 0:
                huawei_positive_ratio = user_stats["positive_huawei"] / user_stats["huawei_mentions"]
                xiaomi_negative_ratio = user_stats["negative_xiaomi"] / user_stats["xiaomi_mentions"]
                brand_bias = huawei_positive_ratio + xiaomi_negative_ratio
                user_stats["brand_bias_score"] = brand_bias

            # 讽刺比例
            sarcasm_ratio = user_stats["sarcasm_count"] / user_stats["total_comments"]
            user_stats["sarcasm_ratio"] = sarcasm_ratio

            # 综合评分
            fanatic_score = extreme_ratio * 0.4 + brand_bias * 0.4 + sarcasm_ratio * 0.2

            # 如果有明显的极端类型偏好，增加分数
            pattern_bias = 0
            if user_stats["comment_pattern"]:
                # 检查是否有特定类型的极端言论出现频率较高
                total_patterns = sum(user_stats["comment_pattern"].values())
                for pattern, count in user_stats["comment_pattern"].items():
                    if count / total_patterns > 0.5:  # 如果某一类型占比超过50%
                        pattern_bias = 0.2
                        break

            fanatic_score += pattern_bias

        return fanatic_score, user_stats

    def update_detection_model(self, false_positives, false_negatives):
        """根据误判样本更新检测模型"""
        # 分析误判样本
        fp_features = self._extract_features_from_samples(false_positives)
        fn_features = self._extract_features_from_samples(false_negatives)

        # 调整特征权重
        for feature, count in fp_features.items():
            if feature in self.feature_weights:
                # 降低导致误判的特征权重
                self.feature_weights[feature] *= max(0.9, 1 - (count / len(false_positives) * 0.2))
                self.logger.info(f"降低特征权重: {feature} -> {self.feature_weights[feature]:.2f}")

        for feature, count in fn_features.items():
            if feature in self.feature_weights:
                # 提高漏判的特征权重
                self.feature_weights[feature] *= min(1.1, 1 + (count / len(false_negatives) * 0.2))
                self.logger.info(f"提高特征权重: {feature} -> {self.feature_weights[feature]:.2f}")

        # 更新阈值
        if false_positives and false_negatives:
            fp_confidences = [sample.get("detection_result", {}).get("confidence", 0) for sample in false_positives]
            fn_confidences = [sample.get("detection_result", {}).get("confidence", 0) for sample in false_negatives]

            avg_fp_confidence = sum(fp_confidences) / len(fp_confidences)
            avg_fn_confidence = sum(fn_confidences) / len(fn_confidences)

            # 调整阈值，在误判和漏判之间找平衡点
            if avg_fp_confidence > 0 and avg_fn_confidence > 0:
                new_threshold = (avg_fp_confidence + avg_fn_confidence) / 2
                old_threshold = self.detection_threshold
                self.detection_threshold = new_threshold
                self.logger.info(f"更新检测阈值: {old_threshold:.2f} -> {new_threshold:.2f}")

        return {
            "feature_weights": self.feature_weights,
            "detection_threshold": self.detection_threshold
        }

    def _extract_features_from_samples(self, samples):
        """从样本中提取特征"""
        feature_counts = {}

        for sample in samples:
            content = sample.get("content", "")
            detection_result = sample.get("detection_result", {})
            matched_patterns = detection_result.get("matched_patterns", {})

            # 统计匹配模式
            for pattern_type in matched_patterns:
                feature_counts[pattern_type] = feature_counts.get(pattern_type, 0) + 1

            # 检查是否包含特定关键词
            for term in self.huawei_special_terms:
                if term in content.lower():
                    feature_counts["huawei_term"] = feature_counts.get("huawei_term", 0) + 1
                    break

            for term in self.xiaomi_special_terms:
                if term in content.lower():
                    feature_counts["xiaomi_term"] = feature_counts.get("xiaomi_term", 0) + 1
                    break

            # 检查情感强度
            sentiment_score = self._analyze_emotional_intensity(content)
            if sentiment_score > 3:
                feature_counts["high_sentiment"] = feature_counts.get("high_sentiment", 0) + 1

            # 检查讽刺
            sarcasm_score = self._detect_sarcasm(content)
            if sarcasm_score > 0.5:
                feature_counts["sarcasm"] = feature_counts.get("sarcasm", 0) + 1

        return feature_counts

    def _detect_sarcasm(self, content):
        """检测讽刺和反讽"""
        if not content: return 0
        sarcasm_score = 0
        processed_content = self._preprocess_text(content)

        # 使用优化后的讽刺/阴阳怪气相关正则表达式
        sarcasm_patterns = [
            r"真(是|的)?(好|棒|强|厉害).*?[呵哈嘻]",
            r"厉害了.*?我的哥",
            r"不愧是.*?",
            r"就这.*?\?",
            r"太(厉害|强|棒)了吧.*?\[doge\]",
            r"可真是.*?(牛|厉害|强)",
            r"笑死.*?人",
            r"有点.*?(意思|东西)",
            r"我们.*?配吗",
            r"这波.*?操作",
            r"高端.*?大气",
            r"一整个.*?离谱",
            r"绝了.*?",
            r"牛啊.*?牛啊",
            r"雷布斯.*?(又|再|还).*?(赢|成功|胜利)",
            r"小米.*?(又|再|还).*?(赢|成功|胜利)",
            r"雷军.*?(又|再|还).*?(赢|成功|胜利)",
            r"(雷军|小米).*?赢麻了",
            r"(雷军|小米).*?赢(麻|嗨|爆)",
            r"(雷军|小米).*?宇宙第一",
            r"(雷军|小米).*?宇宙无敌",
            r"(雷军|小米).*?永远的神"
        ]

        # 检查讽刺模式
        for pattern in sarcasm_patterns:
            if re.search(pattern, processed_content, re.IGNORECASE):
                sarcasm_score += 0.5

        # 检查特定表情组合
        sarcasm_emojis = ["[doge]", "[滑稽]", "[吃瓜]", "[笑哭]", "[阴险]", "🐶", "🐒", "🤡"]
        for emoji in sarcasm_emojis:
            if emoji in content:
                sarcasm_score += 0.3

        # 检查特定标点组合
        if "???" in content or "？？？" in content:
            sarcasm_score += 0.3
        if "!!!" in content or "！！！" in content:
            sarcasm_score += 0.2

        # 上限为2.0
        return min(sarcasm_score, 2.0)

    def _detect_sentiment_conflict(self, content):
        """检测情感冲突（表面积极但实际消极）"""
        if not content: return 0
        conflict_score = 0
        processed_content = self._preprocess_text(content)

        # 计算正面词和负面词的数量
        positive_count = sum(word in processed_content for word in self.positive_words)
        negative_count = sum(word in processed_content for word in self.negative_words)

        # 如果同时包含较多正面词和负面词，可能存在情感冲突
        if positive_count >= 2 and negative_count >= 1:
            conflict_score += 0.5 * min(positive_count, negative_count)

        # 检查特定的情感冲突模式
        conflict_patterns = [
            r"(好|棒|强|厉害).*?(但是|可是|然而|不过)",
            r"(但是|可是|然而|不过).*?(好|棒|强|厉害)",
            r"虽然.*?但是",
            r"看起来.*?实际上",
            r"表面上.*?其实"
        ]

        for pattern in conflict_patterns:
            if re.search(pattern, processed_content):
                conflict_score += 0.5

        # 上限为2.0
        return min(conflict_score, 2.0)

    def _analyze_emoji_sentiment(self, content):
        """分析表情符号的情感"""
        if not content: return 0

        emoji_score = 0

        # B站特有表情的情感映射
        emoji_sentiment = {
            "[doge]": 0.8,  # 讽刺
            "[吃瓜]": 0.5,  # 看热闹
            "[笑哭]": 0.7,  # 嘲笑
            "[滑稽]": 0.9,  # 讽刺
            "[阴险]": 1.0,  # 负面
            "[生气]": 1.0,  # 负面
            "[委屈]": 0.6,  # 负面
            "[捂脸]": 0.5,  # 尴尬
            "[思考]": 0.3,  # 中性
            "[疑惑]": 0.4,  # 中性偏负
            "[喜欢]": -0.5,  # 正面
            "[笑]": -0.3,  # 正面
            "[打call]": -0.7,  # 正面
            "[鼓掌]": -0.6,  # 正面
            "[大哭]": 0.8,  # 负面
            "[偷笑]": 0.6   # 讽刺
        }

        # 统计表情出现次数及其情感得分
        for emoji, sentiment in emoji_sentiment.items():
            count = content.count(emoji)
            if count > 0:
                # 多个相同表情会增强情感
                emoji_score += sentiment * min(count, 3)  # 最多计算3个相同表情

        # 检查Unicode表情符号
        unicode_emojis = re.findall(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F700-\U0001F77F\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF]', content)
        if unicode_emojis:
            # 简单处理：每个Unicode表情增加0.3分
            emoji_score += len(unicode_emojis) * 0.3

        # 上限为2.0
        return min(abs(emoji_score), 2.0)

    def _predict_toxicity(self, text):
        """使用Detoxify模型预测文本的毒性，并结合自定义规则大幅增强检测效果"""
        if not self.detoxify_available or not text:
            return {"is_toxic": False, "toxicity_index": 0.0, "toxic_categories": [], "toxicity_score": 0.0}

        try:
            predictions = self.detoxify_model.predict(text)
            result = {
                "toxic": predictions.get("toxic", 0),
                "severe_toxic": predictions.get("severe_toxic", 0),
                "obscene": predictions.get("obscene", 0),
                "threat": predictions.get("threat", 0),
                "insult": predictions.get("insult", 0),
                "identity_hate": predictions.get("identity_hate", 0)
            }

            # --- 自定义特征评分 ---
            toxicity_score = 0.0
            detected_features = [] # 用于记录触发的特征类型

            # 匹配所有模式并累加分数 (简化匹配逻辑)
            feature_scores = {
                "sarcasm_irony": 0.6,
                "death_related": 0.8,
                "business_criticism": 0.5,
                "emoji_combinations": 0.4, # 单个表情组合的基础分
                 # 新增类别基础分
                "xiaomi_accident_attack": 0.7, # 事故相关基础分高
                "conspiracy_theory": 0.5,
                "competitor_attack": 0.4,
                "user_group_attack": 0.5,
                "generalization_attack": 0.4,
                "extreme_speech": 0.9 # 极端言论基础分高
            }

            processed_text = self._preprocess_text(text)
            for category, patterns in self.all_patterns.items():
                if category not in feature_scores: continue # 只处理有预设分数的特征类别

                category_match_count = 0
                for pattern in patterns:
                    if pattern.search(processed_text):
                        category_match_count += 1
                        # 对特定高危模式额外加分
                        if category == "xiaomi_accident_attack":
                            toxicity_score += 0.3 # 每次匹配事故攻击都额外加分
                        elif category == "extreme_speech":
                             toxicity_score += 0.4
                        elif category == "death_related":
                             toxicity_score += 0.2

                if category_match_count > 0:
                    base_score = feature_scores.get(category, 0.3) # 获取基础分，默认为0.3
                    # 根据匹配次数调整得分，增加权重
                    category_score = base_score * (1 + (category_match_count - 1) * 0.8)
                    toxicity_score += category_score
                    detected_features.append(f"{category}(x{category_match_count})")

            # 检查特定表情组合的特殊处理 (例如大量重复)
            variant_score, detected_variants, _ = self._check_variant_patterns(text)
            if variant_score > 0:
                toxicity_score += variant_score * 0.8 # 变体/符号得分贡献显著提高 (保持)
                detected_features.extend(detected_variants)


            # --- 修正Detoxify预测结果 ---
            # 降低自定义特征评分的影响
            result["toxic"] = min(result["toxic"] + toxicity_score * 1.2, 1.0) # 降低影响
            result["severe_toxic"] = min(result["severe_toxic"] + toxicity_score * 1.0, 1.0) # 降低影响
            result["obscene"] = min(result["obscene"] + toxicity_score * 0.8, 1.0) # 降低影响
            result["threat"] = min(result["threat"] + toxicity_score * 1.1, 1.0) # 降低影响
            result["insult"] = min(result["insult"] + toxicity_score * 1.3, 1.0) # 降低影响
            result["identity_hate"] = min(result["identity_hate"] + toxicity_score * 1.0, 1.0) # 降低影响

            # --- 判断是否有毒 ---
            is_toxic = False
            toxic_categories = []
            # 使用极低的阈值 (保持)
            for category, score in result.items():
                 # 跳过非分数的键
                if not isinstance(score, (int, float)): continue
                threshold = self.toxicity_thresholds.get(category, 0.15) # 默认阈值也很低
                if score >= threshold:
                    is_toxic = True
                    toxic_categories.append(category)

            # 自定义特征分数达到阈值也判定为toxic (阈值保持)
            if toxicity_score >= 0.8: # 特征得分触发阈值 (保持)
                is_toxic = True
                if "特征匹配" not in toxic_categories:
                    toxic_categories.append("特征匹配")

            # --- 计算综合毒性指数 ---
            # 基础毒性得分 (只取严重毒性、威胁、侮辱)
            toxicity_base = sum(
                result.get(category, 0)
                for category in ["severe_toxic", "threat", "insult"]
            ) / 3

            # 综合得分计算: 调整自定义特征评分的权重
            toxicity_index = (
                toxicity_base * 0.20 +          # Detoxify基础分权重提高
                (toxicity_score * 0.80)         # 自定义特征分权重降低
            )
            toxicity_index = min(toxicity_index, 1.0) # 上限为1

            # --- 整理返回结果 ---
            final_result = {
                "is_toxic": is_toxic,
                "toxicity_index": toxicity_index,
                "toxic_categories": list(set(toxic_categories)), # 去重
                "toxicity_score": toxicity_score, # 自定义特征总分
                "detected_features": detected_features, # 触发的特征
                "detoxify_raw": {k: round(v, 4) for k, v in result.items() if isinstance(v, (int, float))} # 保留原始分数（四舍五入）
            }
            return final_result

        except Exception as e:
            self.logger.error(f"Detoxify毒性预测失败: {e}")
            # 返回一个表示失败但结构完整的字典
            return {"is_toxic": False, "toxicity_index": 0.0, "toxic_categories": ["预测失败"], "toxicity_score": 0.0}

    def enhanced_extreme_fan_detection(self, content):
        """
        增强版华为极端粉丝检测（核心检测逻辑）
        整合规则模式匹配、增强版情感分析和基于Detoxify的毒性分析，采用调整后的判定策略。
        """
        if not content or not isinstance(content, str) or len(content.strip()) < 3:
            return False, {"is_extreme": False, "reason": "内容过短或格式不正确", "confidence": 0.0}

        result = {
            "is_extreme": False,
            "confidence": 0.0,
            "reasoning": [],
            "detection_methods": {"traditional_rule": False, "toxicity_analysis": False},
            "matched_patterns": {}, # 记录匹配到的规则模式
            "toxicity_details": {} # 记录毒性分析详情
        }

        # --- 1. 传统规则模式匹配 ---
        traditional_score = 0
        matched_patterns_details = {}
        processed_content = self._preprocess_text(content)
        has_xiaomi_mention = any(kw in processed_content for kw in self.xiaomi_special_terms)

        for category, patterns in self.all_patterns.items():
             # 跳过仅用于毒性分析的类别
            if category in ["sarcasm_irony", "death_related", "business_criticism", "emoji_combinations"]:
                continue

            category_match_count = 0
            matched_in_category = []
            for pattern in patterns:
                if pattern.search(processed_content):
                    category_match_count += 1
                    matched_in_category.append(pattern.pattern) # 记录原始正则字符串

            if category_match_count > 0:
                base_weight = self.feature_weights.get(category, 1.0)
                # 根据匹配次数和是否提及小米调整分数
                category_score = base_weight * (1 + (category_match_count - 1) * 0.5) # 多次匹配加分
                if has_xiaomi_mention and category in ["xiaomi_accident_attack", "competitor_attack", "conspiracy_theory", "user_group_attack", "generalization_attack"]:
                    category_score *= 1.5 # 涉及小米的负面模式权重提高 (保持)
                traditional_score += category_score
                matched_patterns_details[category] = matched_in_category
                result["reasoning"].append(f"规则匹配:{category}(x{category_match_count})")

        # 变体/符号得分也加入传统规则评分
        variant_score, detected_variants, _ = self._check_variant_patterns(content)
        if variant_score > 0:
            traditional_score += variant_score * 1.2 # 变体/符号得分贡献提高 (保持)
            result["reasoning"].append(f"检测到变体/特殊符号(得分贡献:{variant_score * 1.2:.2f})")
            if detected_variants:
                 # 将变体信息添加到 matched_patterns
                matched_patterns_details["variant_symbols"] = detected_variants

        # --- 1.5 增强版情感分析 ---
        sentiment_score = self.enhanced_sentiment_analysis(content)
        if sentiment_score > 3.0:  # 情感强度较高
            # 情感强度贡献到传统规则评分
            sentiment_contribution = min((sentiment_score - 3.0) * 0.5, 2.0)  # 最多贡献2.0分
            traditional_score += sentiment_contribution
            result["reasoning"].append(f"增强版情感分析: 强度={sentiment_score:.2f}, 贡献={sentiment_contribution:.2f}")
            # 将情感分析结果添加到matched_patterns
            matched_patterns_details["high_sentiment"] = [f"情感强度: {sentiment_score:.2f}"]

        is_traditional_extreme = traditional_score >= self.malicious_threshold_rule # 使用调整后的阈值
        result["detection_methods"]["traditional_rule"] = is_traditional_extreme
        result["traditional_score"] = round(traditional_score, 2)
        result["matched_patterns"] = matched_patterns_details

        # --- 2. Detoxify 毒性分析 ---
        toxicity_results = self._predict_toxicity(content)
        is_toxic = toxicity_results.get("is_toxic", False)
        toxicity_index = toxicity_results.get("toxicity_index", 0.0) # 使用调整后的计算方式
        toxicity_score_custom = toxicity_results.get("toxicity_score", 0.0) # 自定义特征分

        result["detection_methods"]["toxicity_analysis"] = is_toxic
        result["toxicity_details"] = toxicity_results # 存储完整毒性分析结果
        if is_toxic:
             result["reasoning"].append(f"毒性分析: 指数={toxicity_index:.2f}, 自定义分={toxicity_score_custom:.2f}, 类别={','.join(toxicity_results.get('toxic_categories',[]))}")


        # --- 3. 结果融合与最终判定 (调整后策略) ---
        final_confidence = 0.0
        # 基础置信度主要来自毒性分析 (调整权重)
        if is_toxic:
            # 毒性指数贡献降低
            final_confidence += toxicity_index * 0.65 # 降低贡献
            # 自定义特征分贡献略微降低
            final_confidence += min(toxicity_score_custom / 5.0, 0.25) # 自定义特征分最高贡献降低

        # 传统规则得分贡献一部分 (保持)
        if is_traditional_extreme:
             final_confidence += min(traditional_score / 8.0, 0.4) # 规则得分最高贡献保持

        # 检测方法数量加成 (保持)
        detection_count = sum(result["detection_methods"].values())
        if detection_count >= 2:
            final_confidence += 0.3 # 两种方法都命中则加0.3置信度

        final_confidence = min(final_confidence, 0.99) # 最高置信度0.99
        result["confidence"] = round(final_confidence, 2)

        # 最终判定 (调整单一方法阈值和严重毒性/威胁的触发条件)
        reasons_for_extreme = []
        if detection_count >= 2:
             reasons_for_extreme.append("规则和毒性分析均命中")
        if detection_count == 1 and final_confidence >= self.confidence_threshold_final: # 使用调整后的阈值
             reasons_for_extreme.append(f"单一方法命中且置信度({final_confidence:.2f})达标")
        # 增加对严重毒性/威胁触发的额外要求
        if is_toxic and ("severe_toxic" in toxicity_results.get("toxic_categories", []) or "threat" in toxicity_results.get("toxic_categories", [])) and toxicity_index >= 0.5:
             reasons_for_extreme.append("检测到严重毒性或威胁(且综合指数>=0.5)")
        if is_traditional_extreme and "xiaomi_accident_attack" in matched_patterns_details and traditional_score >= self.high_risk_score_threshold:
             reasons_for_extreme.append(f"高危模式(小米车祸攻击)且规则得分({traditional_score:.2f})达标")
        if toxicity_score_custom >= self.high_toxicity_score_threshold: # 使用调整后的自定义特征分直接触发阈值
             reasons_for_extreme.append(f"自定义特征分数({toxicity_score_custom:.2f})过高")

        result["is_extreme"] = len(reasons_for_extreme) > 0
        if result["is_extreme"]:
            result["final_judgement_reason"] = " | ".join(reasons_for_extreme)
            # 记录极端类型（可选，可以基于匹配的模式或毒性类别判断）
            result["extreme_types"] = self._determine_extreme_types_from_result(result)

        # 完善推理说明
        if result["reasoning"]:
            result["reasoning_summary"] = " | ".join(result["reasoning"])

        return result["is_extreme"], result

    def _determine_extreme_types_from_result(self, result):
        """根据检测结果推断极端类型"""
        types = set()
        if result.get("matched_patterns"):
            patterns = result["matched_patterns"]
            if "blind_worship" in patterns: types.add("品牌崇拜")
            if "conspiracy_theory" in patterns: types.add("阴谋论")
            if "competitor_attack" in patterns: types.add("竞品攻击")
            if "user_group_attack" in patterns: types.add("用户群体攻击")
            if "generalization_attack" in patterns: types.add("泛化攻击")
            if "nationalism" in patterns: types.add("民族主义")
            if "tech_exaggeration" in patterns: types.add("技术夸大")
            if "extreme_speech" in patterns: types.add("极端言论/诅咒")
            if "xiaomi_accident_attack" in patterns: types.add("幸灾乐祸/事故攻击")
        if result.get("toxicity_details"):
            toxicity = result["toxicity_details"]
            if toxicity.get("is_toxic"):
                if "特征匹配" in toxicity.get("toxic_categories",[]): types.add("讽刺/阴阳怪气")
                if "severe_toxic" in toxicity.get("toxic_categories",[]): types.add("严重毒性")
                if "threat" in toxicity.get("toxic_categories",[]): types.add("威胁")
                if "insult" in toxicity.get("toxic_categories",[]): types.add("侮辱")
                if "identity_hate" in toxicity.get("toxic_categories",[]): types.add("身份仇恨")
        return list(types)

    # --- 保留核心检测接口 detect_huawei_fanatic ---
    def detect_huawei_fanatic(self, content, comment_id=None, user_id=None):
        """
        综合检测华为极端粉丝言论和小米攻击言论 (主要检测接口)
        现在直接调用增强版检测逻辑。
        """
        self.detection_count += 1
        log_prefix = f"[评论ID:{comment_id or '未知'}|用户ID:{user_id or '未知'}]"
        self.logger.info(f"{log_prefix} 开始检测 #{self.detection_count} - 内容长度: {len(content) if content else 0}")
        if content and len(content) <= 100:
            self.logger.info(f"{log_prefix} 原始内容: {content}")
        elif content:
            self.logger.info(f"{log_prefix} 原始内容过长, 开头100字符: {content[:100]}...")

        is_extreme, detection_result = self.enhanced_extreme_fan_detection(content)

        # 构建与之前兼容的输出结构，但包含更丰富的细节
        result = {
            "is_huawei_fanatic": is_extreme, # 保持字段名兼容
            "confidence": detection_result.get("confidence", 0),
            "detection_summary": {}
        }

        if is_extreme:
            self.extreme_count += 1
            self.logger.warning(f"{log_prefix} #{self.detection_count} - 检测到极端言论! 置信度: {result['confidence']:.2f}")
            self.logger.warning(f"{log_prefix} 判定理由: {detection_result.get('final_judgement_reason', 'N/A')}")

            result["detection_summary"] = {
                "detection_methods": detection_result.get("detection_methods", {}),
                "reasoning": detection_result.get("reasoning_summary", ""),
                "extreme_types": detection_result.get("extreme_types", []),
                "rule_score": detection_result.get("traditional_score", 0),
                "matched_patterns": detection_result.get("matched_patterns", {}),
                "toxicity_details": detection_result.get("toxicity_details", {})
            }
            # 记录更详细的日志
            if result["detection_summary"].get("extreme_types"):
                 self.logger.warning(f"{log_prefix} 极端类型: {', '.join(result['detection_summary']['extreme_types'])}")
            if result["detection_summary"].get("matched_patterns"):
                pattern_summary = "; ".join([f"{k}({len(v)})" for k, v in result["detection_summary"]["matched_patterns"].items()])
                self.logger.warning(f"{log_prefix} 匹配模式: {pattern_summary}")
            if result["detection_summary"].get("toxicity_details", {}).get("is_toxic"):
                tox_details = result["detection_summary"]["toxicity_details"]
                self.logger.warning(f"{log_prefix} 毒性分析: 指数={tox_details.get('toxicity_index',0):.2f}, 自定义分={tox_details.get('toxicity_score',0):.2f}, 类别={','.join(tox_details.get('toxic_categories',[]))}")

        else:
            self.logger.info(f"{log_prefix} #{self.detection_count} - 未检测到极端言论. 置信度: {result['confidence']:.2f}")
            if result['confidence'] > 0.4: # 记录置信度较高但未达标的情况
                 self.logger.info(f"{log_prefix} 注意: 置信度较高但未达标. 推理: {detection_result.get('reasoning_summary', 'N/A')}")


        if self.detection_count > 0 and self.detection_count % 100 == 0:
            detection_rate = (self.extreme_count / self.detection_count) * 100
            self.logger.info(f"累计统计: 已检测 {self.detection_count} 条评论, 发现 {self.extreme_count} 条极端言论 (比率: {detection_rate:.2f}%)")

        return result

    # --- 移除或注释掉不再需要/冗余的方法 ---
    # def detect_fanatic_comment(self, content): ... (逻辑已整合)
    # def determine_extreme_types(self, content): ... (逻辑已整合)
    # def llm_based_fanaticism_detection(self, content): ... (逻辑已整合)
    # def _is_huawei_fanatic_comment(self, content): ... (逻辑已整合)
    # def detect_xiaomi_car_extremism(self, content): ... (模式已整合)

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
        if any(kw in video_title.lower() for kw in self.huawei_special_terms):
            huawei_related = True
            context_score += 0.5
            context_info["video_huawei_related"] = True

        # 检查视频标题是否与小米相关
        if any(kw in video_title.lower() for kw in self.xiaomi_special_terms):
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
        if huawei_related and any(kw in content.lower() for kw in self.huawei_special_terms):
            context_score += 0.4
            context_info["comment_huawei_related"] = True

        if xiaomi_related and any(kw in content.lower() for kw in self.xiaomi_special_terms):
            context_score += 0.4
            context_info["comment_xiaomi_related"] = True

        # 4. 分析评论情感与视频主题的一致性
        # 如果视频是关于华为的，而评论对华为持负面态度，可能是竞品粉丝
        # 如果视频是关于小米的，而评论对小米持负面态度，可能是华为极端粉丝
        if huawei_related:
            sentiment_score = self._analyze_emotional_intensity(content)
            if sentiment_score > 3:  # 情感强度较高
                context_score += 0.3
                context_info["high_emotion_huawei_video"] = True

        if xiaomi_related:
            sentiment_score = self._analyze_emotional_intensity(content)
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
                    is_extreme, _ = self.enhanced_extreme_fan_detection(other_content)
                    if is_extreme:
                        extreme_count += 1

            # 如果同一视频下极端评论比例较高，增加权重
            extreme_ratio = extreme_count / min(len(other_comments), 20)
            if extreme_ratio > 0.3:  # 超过30%的评论是极端评论
                context_score += 0.4
                context_info["high_extreme_ratio"] = extreme_ratio

        return context_score, context_info

    def record_false_positive(self, content, detection_result):
        """记录误判样本"""
        try:
            # 确保日志目录存在
            log_dir = "logs"
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)

            # 记录到文件
            false_positives_file = os.path.join(log_dir, "false_positives.jsonl")
            with open(false_positives_file, "a", encoding="utf-8") as f:
                record = {
                    "content": content,
                    "detection_result": detection_result,
                    "timestamp": datetime.now().isoformat()
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

            print(f"已记录误判样本到 {false_positives_file}")
            return True
        except Exception as e:
            print(f"记录误判样本失败: {e}")
            return False

    def record_false_negative(self, content, comment_info=None):
        """记录漏判样本"""
        try:
            # 确保日志目录存在
            log_dir = "logs"
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)

            # 记录到文件
            false_negatives_file = os.path.join(log_dir, "false_negatives.jsonl")
            with open(false_negatives_file, "a", encoding="utf-8") as f:
                record = {
                    "content": content,
                    "comment_info": comment_info or {},
                    "timestamp": datetime.now().isoformat()
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

            print(f"已记录漏判样本到 {false_negatives_file}")
            return True
        except Exception as e:
            print(f"记录漏判样本失败: {e}")
            return False

    def calculate_report_priority(self, comment, detection_result):
        """计算举报优先级"""
        # 基础分数 - 置信度
        base_score = detection_result.get("confidence", 0) * 10  # 0-10分

        # 评论点赞数因素 - 高点赞的有害评论影响更大
        like_count = comment.get("like", 0)
        like_score = min(like_count / 50, 5)  # 最高5分

        # 评论新鲜度 - 优先处理较新的评论
        ctime = comment.get("ctime", time.time())
        age_in_days = (time.time() - ctime) / (24 * 3600)
        freshness_score = max(5 - age_in_days, 0) if age_in_days <= 5 else 0  # 最高5分

        # 用户等级因素 - 高等级用户的有害评论影响更大
        user_level = comment.get("member", {}).get("level_info", {}).get("current_level", 0)
        level_score = min(user_level, 6) * 0.5  # 最高3分

        # 极端类型因素 - 某些极端类型优先处理
        extreme_types = detection_result.get("detection_summary", {}).get("extreme_types", [])
        type_score = 0
        priority_types = ["极端言论/诅咒", "幸灾乐祸/事故攻击", "人身攻击"]
        for t in extreme_types:
            if t in priority_types:
                type_score += 2
        type_score = min(type_score, 6)  # 最高6分

        # 上下文因素 - 如果评论区已经有多条类似评论，优先处理
        context_info = detection_result.get("detection_summary", {}).get("context_info", {})
        context_score = 0
        if context_info.get("toxic_atmosphere", 0) > 0.3:
            context_score += 3  # 评论区氛围已恶化，优先处理
        if context_info.get("high_extreme_ratio", 0) > 0.3:
            context_score += 2  # 极端评论比例高，优先处理

        # 计算总分
        total_score = base_score + like_score + freshness_score + level_score + type_score + context_score

        return total_score

# --- 测试函数更新 ---
def test_xiaomi_car_comments():
    """测试小米车祸相关评论识别"""
    detector = HuaweiFanaticDetector()
    test_comments = [
        "发布的时候 什么都是自研的 比谁谁都强 有点动静就是别人的了[吃瓜][捂眼]挺好 反噬终会到来 🐵别来我这评论[滑稽]在我这评论的🐵 诅咒你一家都会去的很悲惨[滑稽]",
        "任何价格的车都不能是一个移动棺材对吧",
        "大概率就是技术太菜又蜜汁自信",
        "没有如果 啥谎成性",
        "低配还敢开智驾，还是小米的。。。",
        "真可怕，死了人，还🈶人帮车企说话",
        "这su7就是不一样啊，冒出这么理中客来讨论，怎么出事那天换隔壁那车不得短信微博让全世界都知道啊，这米公关压不住了，才出来[吃瓜]，雷大善人的把你们的命也当性价比",
        "小米手机我都不用。",
        "我就说，造手机的造汽车，他不成事他不中用，所以说买了小 米车的要小心只能恨自己，不行咱投降输一半，叫小米回收吧",
        "哎呀，不信任新能源你就不买嘛，信任新能源就买嘛，这群人 在网上喷什么",
        "这回是把股市价格打下来了，雷总的恩情这回也还完了，就是感到可惜，你说你110多的速度吧，在高速上确实不算多快。可见你也没把速度当是信仰，问题是说你不信华子的智能驾驶，我很理解。但是你信小米 的智驾还敢在...",
        "米家洗白的还是多啊，上次问界怎么没这么多理中客",
        "恶臭公司的回旋镖虽迟但到，猕猴们的福报来啦",
        "论真搞笑，出事的是小米，却都在往华为智驾上带，你们的 意思是这车搭载的华为的智驾系统？",
        "买了的赶紧卖吧 不然以后就是废铁价",
        # 新增测试用例
        "小米明面上致敬特斯拉保时捷，但是在营销上，别人汽车发布 ，正常宣传，都被蹭完了还要拿出来和雷军相比，对比拉踩一番，本身新车发布就想看一下有关于这款车的视频，全是一些夸小米雷军的。",
        "不敢说话咯，到底谁家捂嘴捂得最狠啊[大笑][大笑][大笑]",
        "up太多结果推导 我不看好小米汽车 但是真心希望小米汽车能 够成功 小米最大的问题就是米粉 太多人不了解电车 买小米汽车是因为小米和雷军",
        "小米是不掉队，也不主推，那是因为不愿意更多投入研发，拿 什么去主推呢。从这个事故我看出来了，小米汽车还是真能成功，米粉真的信仰已经达到如痴如醉的顶峰阶段了。",
        "得不借用弹幕的一句话，客观分析的天花板，以前我是米粉 ，现在绝对算不上了，，至于说为啥不是米粉了，这几年手机用下来真的很难不脱粉",
        "其实有一部分人群的疑问就是，去年山西那次车祸是新中国第 一次车祸吗？为什么这次的网友都那么那么克制，那么为什么在山西那次热搜那么多，为什么这次车祸三天后才开始有节奏",
        "小米公司的重心全都偏向车了，感觉15u就是个边缘部门随便弄的",
        "自己吃回旋镖就说是被带节奏了[笑哭]北京捂嘴王",
        "小米就是一贴牌公司，什么都插一脚，空调，热水器，电视，电脑，汽车。你说他带动下游产业，新能源市场小米不是先驱者，他更像曾经的腾讯，你先做，市场成熟了我就下场收割。这样的环境真的好吗？你这是品牌霸权。",
        "但是我看新闻，好像每一次小米汽车出问题的貌似都是操作人 的问题，汽车自己本身的问题好像只有一次ota固件推送错了是它自己本身的问题，还真没看到汽车自身问题的。[笑哭]",
        "到现在还有给小米组装厂 靠营销 雷不群 买办的标签，一直在逆风局",
        "月份刚发售：嗨就是一组装车，没啥技术卡没看人家byd华为\n2、6月份：车长的不错，有点小帅\n3、7月份:我计划买汉，又没啥买点\n4、8月份一女性朋友一直说喜欢，我就多了解了一下，看了好多车祸视频。决定以后就买他了\n5、9月份去附近店试驾，开起开不孬\n6、牛逼这车，每一次事故能看的我都看，看看究竟是车的问题还是开车的问题。但是没有一次例外，车没问题。",
        "咋都不讨论，号称智驾的车，连个危险刹车都不做？真的做不 到？[藏狐]",
        "雷圣的恩情还不完\n🖐️   🖐️       🖐️   🖐️      🖐️   🖐️\n  \\😭/            \\😭/           \\😭/\n    👕               👕...",
        # 更隐晦的例子
        "😅😅这公关文写得真好，下次别写了。",
        "只能说懂得都懂，不懂的说了也不懂。",
        "又是熟悉的配方，熟悉的味道。",
        "这评论区画风果然不一样。[doge]",
        "遥遥领先！(不是)", # 反讽
        "我什么都没说，只是发个表情[吃瓜]",
        "等一个反转，总感觉没那么简单。",
        "不是吧阿sir，这也能洗？"
    ]

    print("\\n======= 小米车祸评论及隐晦言论识别测试 (使用 detect_huawei_fanatic) =======")
    detected_count = 0
    for i, comment in enumerate(test_comments):
        # 现在直接调用主检测接口
        is_extreme, result = detector.detect_huawei_fanatic(comment, comment_id=f"test_{i+1}")
        print(f"\\n{i+1}. 评论: {comment[:80]}..." if len(comment) > 80 else f"\\n{i+1}. 评论: {comment}")
        print(f"   识别结果: {'✓ 极端言论' if is_extreme else '✗ 正常言论'}")
        print(f"   置信度: {result.get('confidence', 0):.2f}")
        if is_extreme:
             print(f"   判定理由: {result.get('detection_summary', {}).get('reasoning', 'N/A')}")
             print(f"   极端类型: {', '.join(result.get('detection_summary', {}).get('extreme_types', []))}")
        else:
             # 对于未识别的，也打印推理过程帮助分析
             print(f"   (未达标)推理: {result.get('detection_summary', {}).get('reasoning', 'N/A')}")

        if is_extreme:
            detected_count += 1

    print(f"\\n总结: 共测试 {len(test_comments)} 条评论，识别为极端言论 {detected_count} 条，检出率: {detected_count/len(test_comments)*100:.1f}%")
    print("\\n=======================================================================")

if __name__ == "__main__":
    # 初始化日志 (确保即使不通过 BilibiliCommentDetector 类调用也能记录)
    if not logging.getLogger("HuaweiFanaticDetector").handlers:
         log_dir = "logs"
         if not os.path.exists(log_dir): os.makedirs(log_dir)
         current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
         log_file = os.path.join(log_dir, f"fanatic_detector_test_{current_time}.log")
         logging.basicConfig(level=logging.INFO,
                             format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                             handlers=[logging.FileHandler(log_file, encoding='utf-8'), logging.StreamHandler()])
         logging.info("独立运行测试，初始化日志。")

    test_xiaomi_car_comments()
