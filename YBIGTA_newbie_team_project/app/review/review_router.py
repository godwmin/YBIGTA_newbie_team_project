import os
import pandas as pd
from fastapi import APIRouter, HTTPException
from database.connection import mongo_db
from review_analysis.preprocessing.main import PREPROCESS_CLASSES

router = APIRouter(prefix="/review", tags=["review"])

@router.post("/preprocess/{site_name}")
def preprocess_review_data(site_name: str):
    raw_collection = mongo_db["crawling_data"]
    
    # 1. MongoDB에서 데이터 가져오기
    raw_data = list(raw_collection.find({"site_name": site_name}))
    if not raw_data:
        raw_data = list(raw_collection.find({}, {"_id": 0}))
        if not raw_data:
            raise HTTPException(
                status_code=404, 
                detail="MongoDB 'crawling_data' 컬렉션에 데이터가 없습니다."
            )

    # 2. 전처리기 클래스 가져오기
    processor_cls = PREPROCESS_CLASSES.get(site_name)
    if not processor_cls:
        processor_cls = list(PREPROCESS_CLASSES.values())[0]

    # 3. 전처리기 클래스의 __init__ 인자 처리 (input_path, output_dir 요구 대응)
    dummy_input_path = f"database/reviews_{site_name}.csv"
    dummy_output_dir = "database"
    os.makedirs(dummy_output_dir, exist_ok=True)

    try:
        # __init__ 인자를 요구하는 클래스인 경우 인자 전달
        processor = processor_cls(input_path=dummy_input_path, output_dir=dummy_output_dir)
    except TypeError:
        # 인자가 필요 없는 기본 클래스인 경우
        processor = processor_cls()

    # 4. 데이터프레임 변환 후 전처리 수행
    df = pd.DataFrame(raw_data)
    if "_id" in df.columns:
        df = df.drop(columns=["_id"])
        
    try:
        # 전처리 실행
        if hasattr(processor, "process"):
            processed_df = processor.process(df)
        elif hasattr(processor, "fit_transform"):
            processed_df = processor.fit_transform(df)
        elif hasattr(processor, "run"):
            processed_df = processor.run()
        else:
            processed_df = df

        # 결과 형태 변환 (DataFrame -> dict list)
        if isinstance(processed_df, pd.DataFrame):
            processed_data = processed_df.to_dict(orient="records")
        elif isinstance(processed_df, list):
            processed_data = processed_df
        else:
            processed_data = []

        # 5. MongoDB 'processed_data' 컬렉션에 저장
        processed_collection = mongo_db["processed_data"]
        if processed_data:
            # 기존 _id 제거 안전장치
            for item in processed_data:
                if isinstance(item, dict):
                    item.pop("_id", None)
            processed_collection.insert_many(processed_data)

        return {
            "status": "success",
            "message": f"[{site_name}] 데이터 전처리가 완료되었습니다.",
            "processed_count": len(processed_data)
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"전처리 수행 중 에러 발생: {str(e)}"
        )