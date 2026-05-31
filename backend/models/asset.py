from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Literal
from datetime import datetime

# 🔹 Глобальные перечисления (используются во всех моделях)
AssetType = Literal["laptop", "desktop", "monitor", "printer", "peripheral", "mobile", "other"]
Status = Literal["installed", "in_use", "repair", "retired"]

class AssetCreate(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str = Field(..., min_length=3, max_length=100)
    inventory_number: str = Field(..., min_length=3, max_length=50)
    asset_type: AssetType
    serial_number: str = Field(..., min_length=3, max_length=100)
    mol_user_id: Optional[str] = None
    mol_name: Optional[str] = None
    mac_address: Optional[str] = Field(None, pattern=r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$')
    commission_date: Optional[datetime] = None
    warranty_months: Optional[int] = Field(None, ge=0, le=120)
    warranty_end_date: Optional[datetime] = None
    status: Status = "installed" 
    comments: Optional[str] = None
    location: Optional[str] = None

class AssetUpdate(BaseModel):
    model_config = ConfigDict(extra="allow")
    # ✅ Все поля Optional, но с ПОЛНЫМ сохранением валидаторов из Create
    name: Optional[str] = Field(None, min_length=3, max_length=100)
    inventory_number: Optional[str] = Field(None, min_length=3, max_length=50)
    asset_type: Optional[AssetType] = None       
    serial_number: Optional[str] = Field(None, min_length=3, max_length=100)
    mol_user_id: Optional[str] = None
    mol_name: Optional[str] = None
    mac_address: Optional[str] = Field(None, pattern=r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$')  
    commission_date: Optional[datetime] = None
    warranty_months: Optional[int] = Field(None, ge=0, le=120)  
    warranty_end_date: Optional[datetime] = None
    status: Optional[Status] = None                
    comments: Optional[str] = None
    location: Optional[str] = None

class AssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="allow")
    id: str
    name: str
    inventory_number: str
    asset_type: AssetType 
    serial_number: str
    mol_user_id: Optional[str] = None
    mol_name: Optional[str] = None
    mac_address: Optional[str] = None
    commission_date: Optional[datetime] = None
    warranty_months: Optional[int] = None
    warranty_end_date: Optional[datetime] = None
    status: Status       
    comments: Optional[str] = None
    location: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None