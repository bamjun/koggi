# 배포하기  

## 1. 빌드  

```
uv build
```

## 2. 배포  

```
bash pp.sh test   # 👉 TestPyPI로 업로드
bash pp.sh        # 👉 MainPyPI로 업로드
```

### 테스트서버 테스트

```
uv run pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple koggi==0.1.4.5
```

### 로컬 테스트
```
PYTHONPATH=src uv run python src\\koggi\\cli.py --help
```
