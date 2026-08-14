"""Typed write payloads for HITL. These are business fields, not SQL."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InsertWorkorderInput(_StrictModel):
    assetnum: str = Field(..., min_length=1, max_length=64)
    station_name: str | None = None
    cust_linenum: str | None = None
    current_faildate: str | None = None
    prev_faildate: str | None = None
    total_failure_count: str | None = None
    description: str | None = None
    cust_brand: str | None = None
    cust_subsys: str | None = None
    worktype: str | None = None
    pre_type: str | None = None
    pre_value: str | None = None

    @field_validator("assetnum")
    @classmethod
    def strip_assetnum(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("assetnum 不能为空")
        return text


class UpdateWorkorderInput(_StrictModel):
    workorder_id: str = Field(..., min_length=1, max_length=64)
    assetnum: str | None = None
    station_name: str | None = None
    cust_linenum: str | None = None
    current_faildate: str | None = None
    prev_faildate: str | None = None
    total_failure_count: str | None = None
    description: str | None = None
    cust_brand: str | None = None
    cust_subsys: str | None = None
    worktype: str | None = None
    pre_type: str | None = None
    pre_value: str | None = None

    @model_validator(mode="after")
    def require_one_field(self) -> UpdateWorkorderInput:
        data = self.model_dump(exclude={"workorder_id"}, exclude_none=True)
        if not data:
            raise ValueError("更新工单至少需要一个业务字段")
        return self


class DeleteWorkorderInput(_StrictModel):
    workorder_id: str = Field(..., min_length=1, max_length=64)


class ImportWorkordersInput(_StrictModel):
    source_filename: str = Field(..., min_length=1, max_length=255)
    mode: Literal["replace", "append"] = "replace"

    @field_validator("source_filename")
    @classmethod
    def basename_only(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("source_filename 不能为空")
        if "/" in text or "\\" in text or text in {".", ".."}:
            raise ValueError("source_filename 只能是 raw 目录下的文件名，不能包含路径")
        return text


WRITE_PAYLOAD_SCHEMAS: dict[str, type[_StrictModel]] = {
    "insert_workorder": InsertWorkorderInput,
    "update_workorder": UpdateWorkorderInput,
    "delete_workorder": DeleteWorkorderInput,
    "import_workorders": ImportWorkordersInput,
}
