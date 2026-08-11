from fastapi import APIRouter, HTTPException

from backend.application.advice import advise_maintenance


router = APIRouter(
    prefix="/advice",
    tags=["维修建议"]
)


@router.get("/{assetnum}")
def get_advice(assetnum: str):
    """
    获取某台设备的维修建议。

    第一版基于规则模板生成。
    后续可升级为 RAG + Agent。
    """
    try:
        return advise_maintenance(assetnum)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"维修建议生成失败：{str(e)}")
