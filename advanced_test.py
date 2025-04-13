"""
高级测试脚本 - 华为极端粉丝检测模型全面测试
使用本地Detoxify模型文件进行测试
"""
from model import HuaweiFanaticDetector
import os
import sys
import torch
import time
import json

# 设置环境变量以防止下载
os.environ['HF_DATASETS_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'

# 打印系统信息
print(f"系统信息:")
print(f"- Python版本: {sys.version}")
print(f"- PyTorch版本: {torch.__version__}")
print(f"- CUDA是否可用: {torch.cuda.is_available()}")
print(f"- 当前工作目录: {os.getcwd()}")
print(f"- 已设置离线模式环境变量")

# 检查本地模型文件
model_path = os.path.join(os.path.dirname(__file__), "model", "toxic_original-c1212f89.ckpt")
if os.path.exists(model_path):
    print(f"\n本地Detoxify模型文件存在: {model_path}")
    print(f"模型文件大小: {os.path.getsize(model_path) / (1024*1024):.2f} MB")
    
    # 尝试加载模型验证是否可用
    try:
        print("尝试加载模型文件以验证...")
        checkpoint = torch.load(model_path, map_location=torch.device('cpu'))
        print(f"模型加载成功，包含键: {list(checkpoint.keys())}")
    except Exception as e:
        print(f"模型加载测试失败: {e}")
else:
    print(f"警告：本地Detoxify模型文件不存在: {model_path}")

# 测试评论集
test_comments = [
    # 极端粉丝评论
    {"text": "华为比小米好一万倍，小米就是垃圾", "expected": True, "category": "极端对比"},
    {"text": "华为是中国的骄傲，用小米的都是卖国贼", "expected": True, "category": "民族主义"},
    {"text": "米粉都是脑残，华为才是真正的科技", "expected": True, "category": "攻击用户"},
    {"text": "华为鸿蒙已经遥遥领先，打破了美国技术封锁，安卓和iOS都是垃圾", "expected": True, "category": "技术夸大"},
    {"text": "华为麒麟芯片完全自研，不需要美国技术，已经领先高通和苹果", "expected": True, "category": "技术夸大"},
    {"text": "支持华为就是支持中国，用苹果的都是汉奸", "expected": True, "category": "民族主义"},
    {"text": "小米就是山寨厂，抄袭华为，雷军就是PPT大师", "expected": True, "category": "攻击竞品"},
    {"text": "华为就是宇宙第一，其它品牌看了都要跪", "expected": True, "category": "盲目崇拜"},
    
    # 正常评论
    {"text": "这手机还不错，各有优缺点吧", "expected": False, "category": "正常评价"},
    {"text": "华为手机拍照确实不错，但价格有点贵", "expected": False, "category": "正常评价"},
    {"text": "支持华为，但是也不要盲目吹捧", "expected": False, "category": "理性支持"},
    {"text": "国产手机都在进步，华为小米都有各自优势", "expected": False, "category": "公平比较"},
    {"text": "我觉得华为的系统做得不错，但是应用生态还需要提升", "expected": False, "category": "理性评价"},
    {"text": "华为手机质量确实不错，值得推荐", "expected": False, "category": "正常推荐"},
    {"text": "华为和小米各有千秋，选择适合自己的就好", "expected": False, "category": "中立评价"},
    {"text": "不管是什么品牌，好用就行，不必太纠结", "expected": False, "category": "理性观点"}
]

try:
    print("\n初始化检测器...")
    start_time = time.time()
    detector = HuaweiFanaticDetector()
    print(f"检测器初始化完成，耗时: {time.time() - start_time:.2f}秒")

    print("\n开始测试评论...")
    
    # 统计结果
    correct_count = 0
    total_count = len(test_comments)
    false_positives = []
    false_negatives = []
    
    # 开始测试
    for i, test_case in enumerate(test_comments, 1):
        comment = test_case["text"]
        expected = test_case["expected"]
        category = test_case["category"]
        
        print(f"\n测试 {i}/{total_count} [{category}]")
        print(f"评论: {comment}")
        print(f"预期结果: {'是' if expected else '否'}")
        
        try:
            # 使用综合检测
            start_time = time.time()
            result = detector.detect_huawei_fanatic(comment)
            detect_time = time.time() - start_time
            
            # 获取实际结果
            actual = result["is_huawei_fanatic"]
            confidence = result["confidence"]
            
            # 输出结果
            print(f"实际结果: {'是' if actual else '否'} (置信度: {confidence:.2f}, 耗时: {detect_time:.2f}秒)")
            
            # 检查结果是否符合预期
            if actual == expected:
                print("✓ 结果符合预期")
                correct_count += 1
            else:
                print("✗ 结果不符合预期")
                if actual and not expected:
                    false_positives.append({"text": comment, "category": category, "confidence": confidence})
                elif not actual and expected:
                    false_negatives.append({"text": comment, "category": category, "confidence": confidence})
            
            # 输出详细信息
            if "detection_summary" in result:
                summary = result["detection_summary"]
                
                # 检测方法
                if "detection_methods" in summary:
                    methods_used = []
                    for method, used in summary["detection_methods"].items():
                        if used:
                            methods_used.append(method)
                    if methods_used:
                        print(f"使用的检测方法: {', '.join(methods_used)}")
                
                # 检测理由
                if "reasoning" in summary:
                    print(f"检测理由: {summary['reasoning']}")
                
        except Exception as e:
            print(f"处理评论时出错: {str(e)}")
            import traceback
            print(traceback.format_exc())
    
    # 输出统计结果
    print("\n测试结果统计")
    print(f"总测试案例: {total_count}")
    print(f"正确结果数: {correct_count}")
    print(f"正确率: {(correct_count / total_count) * 100:.2f}%")
    print(f"假阳性数量: {len(false_positives)}")
    print(f"假阴性数量: {len(false_negatives)}")
    
    # 输出假阳性和假阴性案例
    if false_positives:
        print("\n假阳性案例 (误判为极端粉丝):")
        for i, case in enumerate(false_positives, 1):
            print(f"{i}. [{case['category']}] {case['text']} (置信度: {case['confidence']:.2f})")
    
    if false_negatives:
        print("\n假阴性案例 (漏判极端粉丝):")
        for i, case in enumerate(false_negatives, 1):
            print(f"{i}. [{case['category']}] {case['text']} (置信度: {case['confidence']:.2f})")

except Exception as e:
    print(f"初始化或运行时出错: {str(e)}")
    import traceback
    print(traceback.format_exc())

print("\n测试完成！") 