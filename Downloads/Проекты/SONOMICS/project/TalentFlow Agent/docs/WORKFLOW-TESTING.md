# 🧪 Workflow Testing & AI Training Framework

## 🎯 Обзор системы тестирования

TalentFlow Agent использует **многоуровневую систему тестирования** для continuous improvement AI-моделей и валидации бизнес-логики.

### 🔄 Принцип работы

```
┌─────────────────────────────────────────────────────────────┐
│                    Continuous Learning Loop                  │
│                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐      │
│  │   Collect   │───▶│   Analyze   │───▶│   Learn     │      │
│  │    Data     │    │   Results   │    │   & Adapt   │      │
│  └─────────────┘    └─────────────┘    └─────────────┘      │
│         │                   │                   │           │
│         └───────────────────┼───────────────────┘           │
│                             ▼                               │
│                    ┌─────────────┐                          │
│                    │   Improve   │                          │
│                    │   Workflows │                          │
│                    └─────────────┘                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 🧠 AI Training Workflows

### **Workflow 1: Vacancy Analysis Training**

#### Цель
Обучить AI точно извлекать pain points, KPIs и требования из вакансий.

#### Процесс
```yaml
Input: Raw vacancy text (1000+ examples)
Process:
  1. Data Collection: Scrape diverse vacancies
  2. Human Annotation: Label pain points, KPIs, skills
  3. Model Training: Fine-tune on labeled data
  4. Validation: Test on unseen vacancies
  5. Deployment: Update production model

Metrics:
  - Precision: >90% for pain point extraction
  - Recall: >85% for skill identification
  - F1-Score: >87% overall accuracy
```

#### Тестовые сценарии
```python
# Test Case 1: FinTech Startup
vacancy = """
Senior Python Developer for crypto trading platform
Current issues: High latency (2-5 sec), poor error handling
Need: Optimize for 10K+ TPS, implement proper logging
Tech: Python, FastAPI, PostgreSQL, Redis
"""

expected_output = {
    "pain_points": [
        "High latency (2-5 sec)",
        "Poor error handling",
        "Need for high TPS (10K+)"
    ],
    "kpis": [
        "Reduce latency to <500ms",
        "Handle 10K+ TPS",
        "Implement proper logging"
    ],
    "required_skills": ["Python", "FastAPI", "PostgreSQL", "Redis"],
    "urgency_score": 8
}
```

### **Workflow 2: Response Generation Training**

#### Цель
Обучить AI генерировать персонализированные отклики высокого качества.

#### Процесс
```yaml
Input: Analysis results + Company context
Process:
  1. RAG Setup: Vector database of successful responses
  2. Template Creation: Dynamic prompt templates
  3. A/B Testing: Multiple response variations
  4. Performance Tracking: Conversion rates
  5. Model Optimization: Improve based on results

Success Metrics:
  - Response Quality: 4.0+ / 5.0 rating
  - Conversion Rate: 8-12% to meeting
  - Engagement Time: <30 seconds read time
```

#### Тестовые сценарии
```python
# Scenario A: Technical Founder
context = {
    "company_stage": "Series A",
    "founder_background": "Technical",
    "company_size": "50-100",
    "tech_stack": ["Python", "React", "AWS"]
}

# Expected: Technical depth, metrics, architecture discussion

# Scenario B: Non-Technical CEO
context = {
    "company_stage": "Seed",
    "founder_background": "Business",
    "company_size": "10-25",
    "tech_stack": ["No technical background"]
}

# Expected: Business focus, ROI, growth metrics
```

### **Workflow 3: Lead Scoring Training**

#### Цель
Обучить AI точно оценивать приоритет лидов для максимальной эффективности.

#### Процесс
```yaml
Input: Vacancy analysis + Company data
Process:
  1. Historical Analysis: Past successful deals
  2. Feature Engineering: Extract predictive features
  3. Model Training: Classification/regression models
  4. Calibration: Adjust thresholds
  5. Monitoring: Track prediction accuracy

Features:
  - Company size and stage
  - Technical complexity
  - Budget indicators
  - Urgency signals
  - Market conditions
```

---

## 🧪 Testing Frameworks

### **Unit Testing Framework**

#### Vacancy Parser Tests
```python
import pytest
from parsers.djinni_parser import DjinniParser

class TestDjinniParser:
    def test_extract_company_name(self):
        html = "<h1>Senior Python Developer at TechCorp</h1>"
        parser = DjinniParser()
        result = parser.extract_company_name(html)
        assert result == "TechCorp"
    
    def test_extract_salary_range(self):
        html = "<span>$3000-5000</span>"
        parser = DjinniParser()
        result = parser.extract_salary_range(html)
        assert result == {"min": 3000, "max": 5000, "currency": "USD"}
    
    def test_detect_tech_stack(self):
        text = "We need Python, Django, PostgreSQL developer"
        parser = DjinniParser()
        result = parser.detect_tech_stack(text)
        assert "Python" in result
        assert "Django" in result
        assert "PostgreSQL" in result
```

#### AI Analysis Tests
```python
from ai.analyzer import VacancyAnalyzer

class TestVacancyAnalyzer:
    def test_pain_point_extraction(self):
        vacancy = "Our API is slow and crashes under load"
        analyzer = VacancyAnalyzer()
        result = analyzer.extract_pain_points(vacancy)
        assert "slow API" in result
        assert "crashes under load" in result
    
    def test_urgency_scoring(self):
        vacancy = "URGENT: Need developer ASAP for critical project"
        analyzer = VacancyAnalyzer()
        score = analyzer.calculate_urgency(vacancy)
        assert score >= 8
    
    def test_skill_extraction(self):
        vacancy = "Required: 5+ years Python, FastAPI, Docker"
        analyzer = VacancyAnalyzer()
        skills = analyzer.extract_skills(vacancy)
        assert "Python" in skills
        assert "FastAPI" in skills
        assert "Docker" in skills
```

### **Integration Testing Framework**

#### End-to-End Workflow Tests
```python
from workflows.full_pipeline import TalentFlowPipeline

class TestFullPipeline:
    def test_vacancy_to_response_workflow(self):
        pipeline = TalentFlowPipeline()
        
        # Input vacancy
        vacancy_data = {
            "title": "Senior Python Developer",
            "company": "TechCorp",
            "description": "We need to optimize our backend...",
            "source": "djinni.co"
        }
        
        # Execute full workflow
        result = pipeline.process_vacancy(vacancy_data)
        
        # Validate output
        assert result["analysis"]["pain_points"] is not None
        assert result["response"]["text"] is not None
        assert result["score"]["priority"] > 0
        assert result["actions"]["send_response"] is True
    
    def test_lead_scoring_accuracy(self):
        pipeline = TalentFlowPipeline()
        
        # Test cases with known outcomes
        test_cases = [
            {"vacancy": "Senior role, high salary, urgent", "expected_score": 85},
            {"vacancy": "Junior role, low salary, not urgent", "expected_score": 25},
            {"vacancy": "Mid-level, good company, some urgency", "expected_score": 60}
        ]
        
        for case in test_cases:
            actual_score = pipeline.score_lead(case["vacancy"])
            assert abs(actual_score - case["expected_score"]) <= 10
```

### **Performance Testing Framework**

#### Load Testing
```python
import asyncio
import aiohttp
from locust import HttpUser, task, between

class TalentFlowLoadTest(HttpUser):
    wait_time = between(1, 3)
    
    @task
    def analyze_vacancy(self):
        self.client.post("/api/v1/analyze", json={
            "vacancy_text": "Senior Python Developer...",
            "source": "djinni.co"
        })
    
    @task
    def generate_response(self):
        self.client.post("/api/v1/generate", json={
            "analysis_id": "123",
            "candidate_profile": {...}
        })
    
    @task
    def score_lead(self):
        self.client.post("/api/v1/score", json={
            "vacancy_data": {...}
        })
```

#### AI Model Performance Tests
```python
from ai.performance_monitor import ModelPerformanceMonitor

class TestAIModelPerformance:
    def test_response_quality_consistency(self):
        monitor = ModelPerformanceMonitor()
        
        # Generate 100 responses
        responses = []
        for i in range(100):
            response = monitor.generate_response(test_vacancy)
            responses.append(response)
        
        # Check quality distribution
        quality_scores = [r.quality_score for r in responses]
        avg_quality = sum(quality_scores) / len(quality_scores)
        
        assert avg_quality >= 4.0
        assert min(quality_scores) >= 3.0
        assert max(quality_scores) <= 5.0
    
    def test_processing_time_requirements(self):
        monitor = ModelPerformanceMonitor()
        
        start_time = time.time()
        result = monitor.process_vacancy(test_vacancy)
        processing_time = time.time() - start_time
        
        assert processing_time <= 30.0  # Max 30 seconds
```

---

## 📊 A/B Testing Framework

### **Response Variation Testing**

#### Test Setup
```yaml
Test Name: Response_Personalization_v1_vs_v2
Duration: 2 weeks
Sample Size: 500 vacancies
Metrics:
  - Primary: Conversion rate to meeting
  - Secondary: Response quality rating
  - Tertiary: Time to response

Variants:
  A (Control):
    Template: "Standard professional tone"
    Personalization: Basic company research
    CTA: "Let's schedule a call"
  
  B (Treatment):
    Template: "Conversational, data-driven"
    Personalization: Deep company analysis + metrics
    CTA: "30-min technical discussion"
```

#### Implementation
```python
from experiments.ab_test import ABTestManager

class ResponseABTest:
    def __init__(self):
        self.test_manager = ABTestManager()
    
    def assign_variant(self, vacancy_id):
        """Random assignment to A/B variants"""
        return self.test_manager.assign_variant(vacancy_id)
    
    def generate_response(self, vacancy, variant):
        if variant == "A":
            return self.generate_standard_response(vacancy)
        elif variant == "B":
            return self.generate_personalized_response(vacancy)
    
    def track_conversion(self, vacancy_id, variant, outcome):
        """Track if variant led to meeting"""
        self.test_manager.log_event(vacancy_id, {
            "variant": variant,
            "outcome": outcome,
            "timestamp": datetime.utcnow()
        })
```

### **Prompt Optimization Testing**

#### Test Scenarios
```python
# Test 1: Temperature Settings
temperature_tests = [
    {"temp": 0.3, "description": "Conservative, factual"},
    {"temp": 0.7, "description": "Balanced creativity"},
    {"temp": 0.9, "description": "High creativity"}
]

# Test 2: Prompt Templates
prompt_tests = [
    {"template": "formal_business", "style": "Professional"},
    {"template": "conversational_tech", "style": "Technical"},
    {"template": "data_driven", "style": "Metrics-focused"}
]

# Test 3: Context Length
context_tests = [
    {"context_length": "short", "chars": 500},
    {"context_length": "medium", "chars": 1000},
    {"context_length": "long", "chars": 2000}
]
```

---

## 🔍 Quality Assurance Framework

### **Response Quality Checklist**

#### Automated Checks
```python
class ResponseQualityChecker:
    def __init__(self):
        self.checks = [
            self.check_length,
            self.check_tone,
            self.check_cta_presence,
            self.check_personalization,
            self.check_technical_accuracy,
            self.check_grammar
        ]
    
    def check_length(self, response):
        """Ensure response is neither too short nor too long"""
        word_count = len(response.text.split())
        return 50 <= word_count <= 200
    
    def check_tone(self, response):
        """Verify professional but conversational tone"""
        formal_words = ["regarding", "concerning", "furthermore"]
        casual_words = ["hey", "cool", "awesome"]
        
        formal_count = sum(1 for word in formal_words if word in response.text.lower())
        casual_count = sum(1 for word in casual_words if word in response.text.lower())
        
        return formal_count > casual_count
    
    def check_cta_presence(self, response):
        """Ensure clear call-to-action"""
        cta_phrases = ["schedule", "call", "meeting", "discuss", "chat"]
        return any(phrase in response.text.lower() for phrase in cta_phrases)
```

#### Human Review Process
```yaml
Review Workflow:
  1. Automated Screening: Run quality checks
  2. Random Sampling: 10% of responses for human review
  3. Expert Evaluation: Senior recruiter assessment
  4. Feedback Loop: Update prompts based on feedback
  5. Model Retraining: Incorporate approved examples

Review Criteria:
  - Relevance to vacancy (1-5 scale)
  - Personalization level (1-5 scale)
  - Professional tone (1-5 scale)
  - Call-to-action clarity (1-5 scale)
  - Overall quality (1-5 scale)
```

---

## 📈 Continuous Improvement Process

### **Data Collection Pipeline**

```python
class DataCollectionPipeline:
    def __init__(self):
        self.collectors = [
            VacancyCollector(),
            ResponseCollector(),
            OutcomeCollector(),
            FeedbackCollector()
        ]
    
    def collect_daily_data(self):
        """Collect all data for the day"""
        daily_data = {}
        
        for collector in self.collectors:
            data = collector.collect()
            daily_data[collector.name] = data
        
        return daily_data
    
    def analyze_performance(self, data):
        """Analyze performance metrics"""
        metrics = {
            "response_quality": self.calculate_quality_scores(data),
            "conversion_rates": self.calculate_conversions(data),
            "processing_times": self.calculate_processing_times(data),
            "error_rates": self.calculate_error_rates(data)
        }
        return metrics
```

### **Model Retraining Schedule**

```yaml
Retraining Schedule:
  Daily:
    - Collect performance data
    - Update quality metrics
    - Monitor for drift
  
  Weekly:
    - Analyze A/B test results
    - Update prompt templates
    - Review human feedback
  
  Monthly:
    - Full model retraining
    - Performance benchmarking
    - Strategy adjustments
  
  Quarterly:
    - Architecture review
    - Competitive analysis
    - Roadmap updates
```

---

## 🎯 Success Metrics & KPIs

### **AI Performance Metrics**
- **Accuracy**: >90% correct pain point extraction
- **Precision**: >85% relevant response generation
- **Recall**: >80% comprehensive analysis
- **F1-Score**: >85% balanced performance
- **Processing Time**: <30 seconds per vacancy

### **Business Impact Metrics**
- **Response Quality**: 4.0+ / 5.0 average rating
- **Conversion Rate**: 8-12% vacancy to meeting
- **Time Savings**: 90% reduction in manual work
- **Cost Efficiency**: 70% reduction in cost per lead
- **Customer Satisfaction**: NPS > 50

### **Testing Coverage Metrics**
- **Unit Test Coverage**: >90%
- **Integration Test Coverage**: >80%
- **E2E Test Coverage**: >70%
- **A/B Test Significance**: p-value < 0.05
- **Performance Test Pass Rate**: >95%

---

**Создано для TalentFlow Agent** | Version 1.0 | 05.11.2025
