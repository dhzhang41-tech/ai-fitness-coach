# -*- coding: utf-8 -*-
import hashlib
import math

import chromadb
from knowledge.exercises import EXERCISE_LIBRARY


class LocalHashEmbeddingFunction:
    """Small local embedding function to avoid model downloads during deploy.

    ChromaDB's default embedding function downloads an ONNX model on first use.
    That is fragile on small cloud servers, especially when GitHub/model hosts
    are slow or blocked. This hash-based vectorizer is deterministic and good
    enough for the project's small built-in knowledge base.
    """

    def __init__(self, dimensions: int = 384):
        self.dimensions = dimensions

    def name(self) -> str:
        return "local_hash_embedding"

    def __call__(self, input):
        return [self._embed(text) for text in input]

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        normalized = str(text).lower()
        tokens = list(normalized)
        tokens += normalized.split()

        for token in tokens:
            if not token.strip():
                continue
            digest = hashlib.md5(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "little") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[idx] += sign

        norm = math.sqrt(sum(v * v for v in vector))
        if norm == 0:
            return vector
        return [v / norm for v in vector]


_embedding_function = LocalHashEmbeddingFunction()

_client = None
_exercise_collection = None
_principle_collection = None
_recovery_collection = None
_physiology_collection = None
_nutrition_collection = None
_initialized = False

# ─── 1. 训练原则（8条）─ what/why ─────────────────────
TRAINING_KNOWLEDGE = [
    {
        "id": "tp_01",
        "topic": "MEV最低有效训练量",
        "decision_type": "what",
        "trigger_keywords": ["最少练多少", "最低训练量", "维持", "MEV"],
        "source": "RP Strength",
        "confidence": "high",
        "content": "MEV（Minimum Effective Volume）是最低有效训练量，指每个肌群每周至少需要10个有效组才能刺激增长。低于MEV的训练量仅能维持当前肌肉量，无法触发 hypertrophy 信号。新手MEV较低（每个肌群6-8组/周即可），高级训练者MEV更高（可达12-15组/周）。"
    },
    {
        "id": "tp_02",
        "topic": "MRV最大可恢复训练量",
        "decision_type": "what",
        "trigger_keywords": ["最多练多少", "过量训练", "恢复不过来", "MRV"],
        "source": "RP Strength",
        "confidence": "high",
        "content": "MRV（Maximum Recoverable Volume）是最大可恢复训练量，每个肌群每周超过20组会导致恢复不足，反而阻碍增肌。训练量应始终在MEV和MRV之间。随着训练水平提升，MRV会逐渐升高，但仍存在上限。超过MRV会导致皮质醇升高、睡眠变差、关节疼痛等过度训练症状。"
    },
    {
        "id": "tp_03",
        "topic": "渐进超负荷原则",
        "decision_type": "why",
        "trigger_keywords": ["加重量", "进步", "增肌原理", "超负荷", "渐进"],
        "source": "基础训练学",
        "confidence": "high",
        "content": "渐进超负荷是增肌的核心驱动。每次训练应比上次更难，可通过以下方式实现：增加重量（2.5-5kg）、增加组数（每次加1组）、增加次数（在相同重量下多做1-2次）、缩短组间休息（减少15-30秒）。没有渐进就没有持续增长，但应循序渐进避免受伤。"
    },
    {
        "id": "tp_04",
        "topic": "RIR留力训练法",
        "decision_type": "how",
        "trigger_keywords": ["RIR", "留力", "力竭", "极限", "到力竭"],
        "source": "RP Strength",
        "confidence": "high",
        "content": "RIR（Reps In Reserve）是留力训练法，指训练停止时还剩几次能做。新手建议3-4RIR（即还能做3-4次时停止），中级2-3RIR，高级1-2RIR。日常训练不建议练到完全力竭（0RIR），因为力竭后的恢复成本远高于额外收益。力竭可偶尔用于最后1组，不应每组都力竭。"
    },
    {
        "id": "tp_05",
        "topic": "周期化训练安排",
        "decision_type": "when",
        "trigger_keywords": ["周期", "安排", "计划", "循环", "减载"],
        "source": "RP Strength",
        "confidence": "high",
        "content": "推荐3-4周积累期（逐渐加量至接近MRV）后安排1周减载期（降至正常量50-60%）。减载期间保持强度（重量）不变，降低训练量。完成减载后身体超量恢复，可重新开始新周期。积累期每周增加1-2组或轻微增加重量，确保渐进超负荷持续发生。"
    },
    {
        "id": "tp_06",
        "topic": "动作选择优先级",
        "decision_type": "how",
        "trigger_keywords": ["动作选择", "练什么", "动作安排", "顺序", "复合动作"],
        "source": "基础训练学",
        "confidence": "high",
        "content": "每次训练应先做复合动作（如卧推、深蹲、硬拉），再做孤立动作（如飞鸟、弯举）。复合动作调动更多肌群、消耗大、神经系统要求高，安排在体力最充沛时。先复合后孤立的顺序能最大化训练效果并降低受伤风险。每个肌群建议2-4个动作，总量10-20组。"
    },
    {
        "id": "tp_07",
        "topic": "组间休息时间指南",
        "decision_type": "how",
        "trigger_keywords": ["休息多久", "组间休息", "间歇", "休息时间"],
        "source": "基础训练学",
        "confidence": "high",
        "content": "力量训练（1-5RM）：休息2-3分钟，确保ATP完全恢复。肌肥大训练（6-15RM）：休息1-2分钟，保持代谢压力。耐力训练（15RM+）：休息30-60秒。休息不足会影响下组质量和重量输出，休息过长会降低训练密度。建议用计时器严格控制，不要凭感觉休息。"
    },
    {
        "id": "tp_08",
        "topic": "训练频率建议",
        "decision_type": "what",
        "trigger_keywords": ["频率", "一周练几次", "分化", "PPL", "推拉腿"],
        "source": "RP Strength",
        "confidence": "high",
        "content": "每个肌群每周受训2次是最佳频率。三分化（Push/Pull/Legs）适合每周训练3-6天的中级用户，每个肌群每5天受训2次。四分化（Upper/Lower）适合每周4天，上下肢交替。新手建议全身训练每周3次，每个动作做2-3组即可有效刺激增长。"
    },
]

# ─── 2. 动作技术要点（9条）─ how ─────────────────────
TECHNIQUE_KNOWLEDGE = [
    {
        "id": "tech_01",
        "topic": "热身策略",
        "decision_type": "how",
        "trigger_keywords": ["热身", "激活", "准备活动", "动态拉伸"],
        "source": "基础训练学",
        "confidence": "high",
        "content": "训练前应进行5-10分钟热身：先做轻量有氧或动态拉伸提升心率，然后做目标肌群的激活动作（如弹力带肩环绕、臀桥），最后用正式动作的50%重量做2-3组热身组。热身组不做到力竭，目的是促进血液流向目标肌群并激活神经系统。"
    },
    {
        "id": "tech_02",
        "topic": "核心收紧与腹内压",
        "decision_type": "how",
        "trigger_keywords": ["核心", "收紧", "腹内压", "腰带", "憋气"],
        "source": "基础训练学",
        "confidence": "high",
        "content": "大重量训练时核心收紧至关重要：深吸气到腹部（不是胸部），腹壁向外撑开形成腹内压，然后憋气完成动作的向心阶段，动作完成后呼气。全程保持脊柱中立位，不要拱背或过度反弓。使用腰带能增加约10-20%的腹内压，但不应依赖腰带忽视核心训练。"
    },
    {
        "id": "tech_03",
        "topic": "训练节奏（Tempo）",
        "decision_type": "how",
        "trigger_keywords": ["节奏", "速度", "离心", "向心", "慢放", "控制"],
        "source": "RP Strength",
        "confidence": "high",
        "content": "推荐节奏为3/0/1/0（离心3秒、底部无停顿、向心1秒、顶部无停顿）。慢速离心（3-4秒）增加肌肉张力时间，促进微损伤和超量恢复。不要利用惯性完成动作，每个rep都应有控制。肌肥大训练尤其注重离心控制，力量训练可适当加快向心速度。"
    },
    {
        "id": "tech_04",
        "topic": "念动一致（Mind-Muscle Connection）",
        "decision_type": "how",
        "trigger_keywords": ["念动", "意念", "感受", "发力感", "Mind-Muscle"],
        "source": "RP Strength",
        "confidence": "medium",
        "content": "训练时应专注感受目标肌群的收缩和拉伸，而非只关注移动重量。研究显示念动一致能增加目标肌群的肌电活动10-20%。轻重量时容易建立念动一致，大重量时优先保证力学结构正确。如果某个动作始终找不到发力感，降低重量、放慢节奏重新建立连接。"
    },
    {
        "id": "tech_05",
        "topic": "全幅度训练（Full ROM）",
        "decision_type": "how",
        "trigger_keywords": ["幅度", "ROM", "半程", "全程", "全幅度", "拉伸"],
        "source": "基础训练学",
        "confidence": "high",
        "content": "全幅度训练比半程训练增肌效果更好，因为肌肉在拉伸位（长长度）的机械张力对肌肥大至关重要。在安全前提下，应完成关节允许的最大幅度。例如深蹲蹲到大腿平行或更低（髋低于膝），卧推杠铃触胸，硬拉每次从地面拉起。关节活动度不足时先改善活动度。"
    },
    {
        "id": "tech_06",
        "topic": "瓦尔萨尔瓦呼吸法",
        "decision_type": "how",
        "trigger_keywords": ["呼吸", "憋气", "瓦尔萨瓦", "发力呼吸"],
        "source": "基础训练学",
        "confidence": "high",
        "content": "大重量复合动作（深蹲、硬拉、卧推）应使用瓦尔萨尔瓦呼吸法：动作开始前深吸气→憋气完成向心阶段→动作完成后呼气。此法通过增加腹内压保护脊柱，能多输出5-10%力量。高血压患者慎用。轻重量训练可使用正常呼吸节奏：离心吸气、向心呼气。"
    },
    {
        "id": "tech_07",
        "topic": "保护与扶助",
        "decision_type": "how",
        "trigger_keywords": ["保护", "辅助", "扶助", "帮补", "安全"],
        "source": "基础训练学",
        "confidence": "medium",
        "content": "大重量卧推和深蹲必须有人保护或使用保护架。保护者应站在训练者头侧（卧推）或身后（深蹲），双手接近但不接触杠铃，仅在训练者力竭时提供最小必要助力。助力重量不宜过大，应让训练者完成动作主体。每组结束后杠铃安全归位再松手。"
    },
    {
        "id": "tech_08",
        "topic": "握法与握力",
        "decision_type": "how",
        "trigger_keywords": ["握法", "握力", "正握", "反握", "勾握", "助力带"],
        "source": "基础训练学",
        "confidence": "high",
        "content": "背部训练推荐正握（手心朝后）以最大化背阔肌参与。硬拉推荐正反握或勾握防止杠铃滑落。助力带在握力不足时使用，但不要过早依赖，握力本身也是训练指标之一。推类动作手腕保持中立对齐前臂，不要向后折叠。握距不同影响受力部位，宽握侧重外侧，窄握侧重内侧。"
    },
    {
        "id": "tech_09",
        "topic": "粘滞点突破技巧",
        "decision_type": "fix",
        "trigger_keywords": ["粘滞点", "卡住", "起不来", "推不动", "粘住"],
        "source": "RP Strength",
        "confidence": "high",
        "content": "粘滞点是动作全程中最弱的环节。突破方法：1）针对粘滞点做半程训练（如卧推在底部推不起就做上半程），2）使用超负荷离心（比向心重10-20%），3）做针对性辅助训练加强弱点肌群（如卧推粘滞点加强三头），4）在粘滞点位置做等长收缩（静力5秒）。"
    },
]

# ─── 3. 恢复管理（7条）─ when/fix ─────────────────────
RECOVERY_KNOWLEDGE_STRUCTURED = [
    {
        "id": "rec_01",
        "topic": "睡眠与训练表现",
        "decision_type": "why",
        "trigger_keywords": ["睡眠", "熬夜", "失眠", "睡不够", "皮质醇"],
        "source": "ISSN",
        "confidence": "high",
        "content": "睡眠不足6小时使皮质醇升高20%以上，直接抑制睾酮分泌，导致力量下降5-10%。睡眠是训练表现最重要的预测指标——比训练计划本身更重要。建议每晚7-9小时高质量睡眠，固定作息时间，睡前1小时避免屏幕蓝光。睡眠质量差时建议降低训练强度而非直接跳过训练。"
    },
    {
        "id": "rec_02",
        "topic": "减载触发条件",
        "decision_type": "when",
        "trigger_keywords": ["减载", "deload", "需要减载", "什么时候减载"],
        "source": "RP Strength",
        "confidence": "high",
        "content": "以下情况应主动安排减载周：1）连续两周训练表现未提升甚至下降（重量/次数/组数停滞或退步），2）主观疲劳感持续偏高（RPE连续多日≥8），3）睡眠质量明显下降，4）关节或肌腱出现持续性酸痛。建议每3-4周积累期后自动安排1周减载，不必等出现症状再行动。"
    },
    {
        "id": "rec_03",
        "topic": "主动恢复方法",
        "decision_type": "how",
        "trigger_keywords": ["主动恢复", "恢复方法", "放松", "冷身", "拉伸"],
        "source": "ISSN",
        "confidence": "high",
        "content": "训练后低强度有氧（心率120-130bpm，10-15分钟）比完全休息更能促进血液循环，加速代谢废物清除，减少DOMS。训练后静态拉伸保持30秒以上，重点拉伸训练的目标肌群。泡沫轴滚压可缓解筋膜紧张，每个部位滚压30-60秒。冷热水交替浴（冷1分热3分，循环3次）有助减少炎症。"
    },
    {
        "id": "rec_04",
        "topic": "DOMS延迟性肌肉酸痛",
        "decision_type": "what",
        "trigger_keywords": ["DOMS", "酸痛", "延迟性", "肌肉酸痛", "疼", "练完疼"],
        "source": "ISSN",
        "confidence": "high",
        "content": "DOMS通常在训练后24-72小时达到高峰，是肌肉微损伤和炎症反应的正常表现，与增肌效果不成正比。DOMS严重不代表训练效果好，不酸痛也不代表训练无效。轻度DOMS不影响训练效果，可以照常训练但降低涉及该肌群的动作重量。重度DOMS建议改为轻量有氧或休息一天。"
    },
    {
        "id": "rec_05",
        "topic": "精神压力管理",
        "decision_type": "fix",
        "trigger_keywords": ["压力", "焦虑", "紧张", "心态", "情绪", "皮质醇"],
        "source": "ISSN",
        "confidence": "high",
        "content": "高精神压力状态下皮质醇升高抑制合成代谢，即使训练计划和饮食都完美，增肌效果也会打折扣。长期高压建议：1）降低训练强度而非放弃训练（轻量训练有助于缓解压力），2）缩短训练时间控制在45分钟内，3）减少高神经系统要求的动作（如大重量深蹲），4）增加散步等低强度活动。"
    },
    {
        "id": "rec_06",
        "topic": "过度训练识别",
        "decision_type": "fix",
        "trigger_keywords": ["过度训练", "疲劳积累", "倦怠", "练不动", "burnout"],
        "source": "RP Strength",
        "confidence": "high",
        "content": "过度训练的症状包括：持续疲劳感、训练欲望下降、力量/耐力下降、睡眠质量变差、静息心率升高5bpm以上、食欲下降、情绪波动频繁。出现上述3项以上症状应立即停止高强度训练，安排至少5-7天完全休息或只做低强度活动。恢复后从减载量（正常50%）重新开始，不要直接回到峰值。"
    },
    {
        "id": "rec_07",
        "topic": "柔韧性与活动度",
        "decision_type": "how",
        "trigger_keywords": ["柔韧", "活动度", "灵活", "拉伸", "僵硬", "卡住"],
        "source": "基础训练学",
        "confidence": "medium",
        "content": "关节活动度不足直接影响训练质量和安全。深蹲蹲不下去常因踝关节或髋关节活动度不足，卧推肩膀痛常因胸椎活动度差或肩袖紧张。每天做5-10分钟针对性活动度训练效果优于只在训练前拉伸。重点区域：胸椎伸展、髋关节屈曲和外旋、踝关节背屈。持久的改善需要6-12周持续坚持。"
    },
]

# ─── 4. 生理学基础（5条）─ why ────────────────────────
PHYSIOLOGY_KNOWLEDGE = [
    {
        "id": "phy_01",
        "topic": "肌肉蛋白质合成（MPS）",
        "decision_type": "why",
        "trigger_keywords": ["肌肉合成", "MPS", "蛋白质合成", "增肌原理"],
        "source": "ISSN",
        "confidence": "high",
        "content": "肌肉蛋白质合成（MPS）是增肌的分子基础。训练通过机械张力触发mTOR信号通路，激活MPS。MPS在训练后24小时内升高，48-72小时恢复基线。每次训练刺激MPS约24-36小时，因此每天摄入足量蛋白质以维持合成状态至关重要。MPS存在上限，单次训练超过一定量不会额外增加MPS。"
    },
    {
        "id": "phy_02",
        "topic": "训练激素反应",
        "decision_type": "why",
        "trigger_keywords": ["激素", "睾酮", "生长激素", "皮质醇", "内分泌"],
        "source": "ISSN",
        "confidence": "high",
        "content": "训练引起急性激素反应：睾酮和生长激素短暂升高促进合成代谢，皮质醇同时升高分解代谢。力量训练后睾酮可升高30-100%但2小时内回基线。代谢压力（乳酸堆积）促进生长激素分泌。长期看，持续训练改善激素基线水平，但单次训练的急性激素反应对增肌的直接作用有限，更重要的因素是机械张力和营养。"
    },
    {
        "id": "phy_03",
        "topic": "能量系统与训练",
        "decision_type": "why",
        "trigger_keywords": ["能量系统", "ATP", "肌酸", "糖酵解", "有氧"],
        "source": "基础训练学",
        "confidence": "high",
        "content": "大重量力量训练（1-5RM）主要依赖ATP-PCr系统（快速供能6-10秒），需要2-3分钟完全恢复。肌肥大训练（6-15RM）依赖糖酵解系统（供能30-60秒），产生乳酸堆积，需要1-2分钟恢复。训练中碳水摄入帮助维持糖原水平，低碳饮食会显著影响高强度训练表现。力量训练后做有氧会干扰mTOR信号通路。"
    },
    {
        "id": "phy_04",
        "topic": "肌纤维类型与训练",
        "decision_type": "why",
        "trigger_keywords": ["肌纤维", "快肌", "慢肌", "红肌", "白肌", "I型", "II型"],
        "source": "基础训练学",
        "confidence": "high",
        "content": "人体肌肉由快肌（II型，爆发力）和慢肌（I型，耐力）组成，比例遗传决定但可部分转化。快肌纤维增肌潜力最大但对疲劳敏感，需要大重量（≥75%1RM）或高输出功率刺激。慢肌纤维对低强度高次数更敏感。因此训练应覆盖不同负荷范围：大重量低次数（3-6RM）+中等重量中次数（8-15RM）全面刺激各型肌纤维。"
    },
    {
        "id": "phy_05",
        "topic": "神经适应与力量增长",
        "decision_type": "why",
        "trigger_keywords": ["神经适应", "新手福利期", "力量增长快", "神经驱动"],
        "source": "基础训练学",
        "confidence": "high",
        "content": "训练前几周的力量增长主要来自神经适应而非肌肉变大。神经系统学会更高效地募集运动单位、提高发放频率、减少拮抗肌共收缩。这是新手福利期的生理基础——不增肌也能快速涨力量。神经适应约持续8-12周后进入平台期，此后力量增长更依赖肌肉横截面积增大（即真正的增肌）。"
    },
]

# ─── 5. 营养基础（5条）─ what/how ─────────────────────
NUTRITION_KNOWLEDGE = [
    {
        "id": "nut_01",
        "topic": "蛋白质摄入指南",
        "decision_type": "how",
        "trigger_keywords": ["蛋白质", "蛋白", "摄入量", "吃多少蛋白", "粉"],
        "source": "ISSN",
        "confidence": "high",
        "content": "增肌人群每日蛋白质摄入建议1.6-2.2g/kg体重（75kg的人需要120-165g/天）。每餐20-40g蛋白质能最大化MPS刺激，推荐每日3-4餐均匀分配蛋白质。训练后30分钟内摄入20-40g蛋白质（约1-2勺蛋白粉或100-200g鸡胸肉）最大化训练后合成窗口。植物蛋白吸收率略低于动物蛋白，建议增加10-20%摄入量。"
    },
    {
        "id": "nut_02",
        "topic": "热量盈余与增肌",
        "decision_type": "what",
        "trigger_keywords": ["热量", "卡路里", "多吃", "增肌期", "干净增肌"],
        "source": "ISSN",
        "confidence": "high",
        "content": "增肌需要每日200-500大卡的热量盈余（TDEE基础上）。盈余过小（<200大卡）增肌速度慢，盈余过大（>500大卡）增脂比例增加。干净增肌建议每天TDEE+300大卡，每周体重增长0.25-0.5%。体重上涨太快说明盈余过大，应减少碳水或脂肪摄入。增肌期也应关注食物质量而非只关注热量数字。"
    },
    {
        "id": "nut_03",
        "topic": "训练前后营养",
        "decision_type": "when",
        "trigger_keywords": ["练前吃", "练后吃", "训练前餐", "训练后餐", "加餐"],
        "source": "ISSN",
        "confidence": "high",
        "content": "训练前2-3小时摄入碳水+蛋白质的平衡餐（如米饭+鸡胸+蔬菜）确保能量充足。训练前30分钟可补充快速碳水（香蕉、白面包）提升表现。训练后立即补充20-40g蛋白质+快速碳水（蛋白粉+香蕉/白米），利用胰岛素升高促进肌肉蛋白质合成。睡前摄入酪蛋白（如希腊酸奶、茅屋奶酪）提供缓释氨基酸。"
    },
    {
        "id": "nut_04",
        "topic": "水分与电解质",
        "decision_type": "how",
        "trigger_keywords": ["喝水", "水分", "脱水", "补水", "电解质"],
        "source": "ISSN",
        "confidence": "high",
        "content": "水分流失超过体重2%会导致力量下降5-10%和心率升高。训练前2小时饮水500ml，训练中每10-15分钟饮水150-300ml。高强度训练超过1小时需补充电解质（钠、钾、镁），可用电解质饮料或淡盐水。尿液颜色是简单可靠的脱水指标——淡黄色为正常，深黄色需补水，透明无色可减少饮水。"
    },
    {
        "id": "nut_05",
        "topic": "常见补剂使用建议",
        "decision_type": "how",
        "trigger_keywords": ["补剂", "肌酸", "蛋白粉", "BCAA", "氮泵", "谷氨酰胺"],
        "source": "ISSN",
        "confidence": "high",
        "content": "经科学证实的有效补剂：1）肌酸一水合物（5g/天，唯一A级证据增肌补剂，提升力量和肌肉量2-8%），2）蛋白粉（方便补充蛋白质，但非必须），3）咖啡因（3-6mg/kg，训练前30-60分钟，提升力量和输出功率）。不推荐：BCAA（已摄入足够蛋白质时无额外收益）、谷氨酰胺（无增肌证据）、睾酮促泌剂（无效果）。"
    },
]


def _ensure_collections():
    global _client, _exercise_collection, _principle_collection, _recovery_collection
    global _physiology_collection, _nutrition_collection, _initialized
    if _initialized:
        return
    if _client is None:
        _client = chromadb.EphemeralClient()
        _exercise_collection = _client.get_or_create_collection(
            "exercise_library",
            embedding_function=_embedding_function,
        )
        _principle_collection = _client.get_or_create_collection(
            "training_principles",
            embedding_function=_embedding_function,
        )
        _recovery_collection = _client.get_or_create_collection(
            "recovery_knowledge",
            embedding_function=_embedding_function,
        )
        _physiology_collection = _client.get_or_create_collection(
            "physiology",
            embedding_function=_embedding_function,
        )
        _nutrition_collection = _client.get_or_create_collection(
            "nutrition_basics",
            embedding_function=_embedding_function,
        )

        # ─── Insert training principles (8条) ────────────
        ids, documents, metadatas = [], [], []
        for kb in TRAINING_KNOWLEDGE:
            ids.append(kb["id"])
            documents.append(kb["content"])
            metadatas.append({
                "topic": kb["topic"],
                "decision_type": kb["decision_type"],
                "keywords": ",".join(kb["trigger_keywords"]),
                "source": kb["source"],
                "confidence": kb["confidence"],
            })
        _principle_collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

        # ─── Insert exercise technique (9条 + 20个动作) ──
        ids, documents, metadatas = [], [], []
        for kb in TECHNIQUE_KNOWLEDGE:
            ids.append(kb["id"])
            documents.append(kb["content"])
            metadatas.append({
                "topic": kb["topic"],
                "decision_type": kb["decision_type"],
                "keywords": ",".join(kb["trigger_keywords"]),
                "source": kb["source"],
                "confidence": kb["confidence"],
            })
        # Add EXERCISE_LIBRARY items into exercise_technique collection
        for i, ex in enumerate(EXERCISE_LIBRARY):
            content = f"动作：{ex['name_cn']}（{ex['name_en']}）\n"
            content += f"类别：{ex['category']}\n"
            content += f"主要肌肉：{'、'.join(ex['primary_muscles'])}\n"
            content += "要点：\n" + "\n".join(f"- {p}" for p in ex['key_points']) + "\n"
            content += "常见错误：\n" + "\n".join(f"- {m}" for m in ex['common_mistakes']) + "\n"
            content += f"提示口诀：{'，'.join(ex['cues'])}"
            ids.append(f"ex_{i}")
            documents.append(content)
            metadatas.append({
                "topic": f"动作库-{ex['name_cn']}",
                "decision_type": "how",
                "keywords": f"{ex['name_cn']},{ex['name_en']},{','.join(ex['primary_muscles'])}",
                "source": "动作库",
                "confidence": "high",
                "name_cn": ex["name_cn"],
                "name_en": ex["name_en"],
                "category": ex["category"],
            })
        _exercise_collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

        # ─── Insert recovery knowledge (7条) ────────────
        ids, documents, metadatas = [], [], []
        for kb in RECOVERY_KNOWLEDGE_STRUCTURED:
            ids.append(kb["id"])
            documents.append(kb["content"])
            metadatas.append({
                "topic": kb["topic"],
                "decision_type": kb["decision_type"],
                "keywords": ",".join(kb["trigger_keywords"]),
                "source": kb["source"],
                "confidence": kb["confidence"],
            })
        _recovery_collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

        # ─── Insert physiology (5条) ────────────────────
        ids, documents, metadatas = [], [], []
        for kb in PHYSIOLOGY_KNOWLEDGE:
            ids.append(kb["id"])
            documents.append(kb["content"])
            metadatas.append({
                "topic": kb["topic"],
                "decision_type": kb["decision_type"],
                "keywords": ",".join(kb["trigger_keywords"]),
                "source": kb["source"],
                "confidence": kb["confidence"],
            })
        _physiology_collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

        # ─── Insert nutrition (5条) ─────────────────────
        ids, documents, metadatas = [], [], []
        for kb in NUTRITION_KNOWLEDGE:
            ids.append(kb["id"])
            documents.append(kb["content"])
            metadatas.append({
                "topic": kb["topic"],
                "decision_type": kb["decision_type"],
                "keywords": ",".join(kb["trigger_keywords"]),
                "source": kb["source"],
                "confidence": kb["confidence"],
            })
        _nutrition_collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

        _initialized = True


def init_knowledge_base() -> None:
    _ensure_collections()


# ─── 原始3个检索函数（签名不变）───────────────────────────

def search_exercises(query: str, n_results: int = 3) -> list[str]:
    _ensure_collections()
    results = _exercise_collection.query(query_texts=[query], n_results=n_results)
    return results["documents"][0] if results["documents"] else []


def search_training_principles(query: str, n_results: int = 3) -> list[str]:
    _ensure_collections()
    results = _principle_collection.query(query_texts=[query], n_results=n_results)
    return results["documents"][0] if results["documents"] else []


def search_recovery_knowledge(query: str, n_results: int = 3) -> list[str]:
    _ensure_collections()
    results = _recovery_collection.query(query_texts=[query], n_results=n_results)
    return results["documents"][0] if results["documents"] else []


# ─── 新增4个检索函数 ─────────────────────────────────────

def search_physiology(query: str, n_results: int = 3) -> list[str]:
    """检索生理学知识"""
    _ensure_collections()
    results = _physiology_collection.query(query_texts=[query], n_results=n_results)
    return results["documents"][0] if results["documents"] else []


def search_nutrition(query: str, n_results: int = 3) -> list[str]:
    """检索营养知识"""
    _ensure_collections()
    results = _nutrition_collection.query(query_texts=[query], n_results=n_results)
    return results["documents"][0] if results["documents"] else []


def search_by_decision_type(
    query: str,
    decision_type: str,
    collections: list[str] = None,
    n_results: int = 3,
) -> list[str]:
    """按 decision_type 过滤并语义检索

    参数：
        query: 语义检索文本
        decision_type: 过滤类型（what/why/how/when/fix）
        collections: 指定检索哪些集合，None 时检索全部5个
        n_results: 每个集合返回条数，最终合并后截断

    返回：去重后的 document 内容列表
    """
    _ensure_collections()
    coll_map = {
        "training_principles": _principle_collection,
        "exercise_technique": _exercise_collection,
        "recovery_management": _recovery_collection,
        "physiology": _physiology_collection,
        "nutrition_basics": _nutrition_collection,
    }
    target = collections or list(coll_map.keys())
    results = []
    for name in target:
        coll = coll_map.get(name)
        if not coll:
            continue
        try:
            r = coll.query(
                query_texts=[query],
                n_results=n_results,
                where={"decision_type": decision_type},
            )
            docs = r.get("documents", [[]])[0]
            results.extend(docs)
        except Exception:
            pass
    return results[:n_results]


def search_all(query: str, n_results_per_source: int = 2) -> list[str]:
    """跨所有5个集合检索，合并后去重返回"""
    _ensure_collections()
    all_results = []
    for fn in [
        search_training_principles,
        search_exercises,
        search_recovery_knowledge,
        search_physiology,
        search_nutrition,
    ]:
        try:
            all_results.extend(fn(query, n_results_per_source))
        except Exception:
            pass
    seen = set()
    deduped = []
    for r in all_results:
        if r not in seen:
            seen.add(r)
            deduped.append(r)
    return deduped
