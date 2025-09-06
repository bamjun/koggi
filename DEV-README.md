# 개발 가이드

## 1. 빌드

```
uv build
```

## 2. 배포

```
bash pp.sh test   # TestPyPI에 배포
bash pp.sh        # PyPI에 배포
```

## 3. 로컬 실행

```
PYTHONPATH=src uv run python -m koggi.cli --help
PYTHONPATH=src uv run python -m koggi.cli config list
```

또는 설치 후:

```
uv run koggi --help
```
