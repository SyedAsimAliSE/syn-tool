"""Configuration management."""

from pathlib import Path
from typing import Optional
from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()

class ShopifyConfig(BaseModel):
    """Shopify configuration."""
    shop_url: str
    access_token: str
    api_version: str = "2024-01"  # Latest stable version

class SAPConfig(BaseModel):
    """SAP configuration."""
    api_url: str
    company_db: str
    username: str
    password: str
    verify_ssl: bool = True
    service_layer_url: Optional[str] = None
    warehouse: str = "01"  # Default warehouse
    branch_id: str = "1"  # Default branch
    tax_code: str = "X0"  # Default tax code
    revenue_account: str = "410000"  # Default revenue account
    default_customer_group: int = 100  # Default customer group
    bp_series: Optional[int] = None  # Business Partner series

    @classmethod
    def from_env(cls) -> "SAPConfig":
        """Create SAP configuration from environment variables."""
        return cls(
            api_url=os.getenv("SAP_API_URL"),
            company_db=os.getenv("SAP_COMPANY_DB"),
            username=os.getenv("SAP_USERNAME"),
            password=os.getenv("SAP_PASSWORD"),
            verify_ssl=os.getenv("SAP_VERIFY_SSL", "true").lower() == "true",
            service_layer_url=os.getenv("SAP_SERVICE_LAYER_URL"),
            warehouse=os.getenv("SAP_WAREHOUSE", "01"),
            branch_id=os.getenv("SAP_BRANCH_ID", "1"),
            tax_code=os.getenv("SAP_TAX_CODE", "X0"),
            revenue_account=os.getenv("SAP_REVENUE_ACCOUNT", "410000"),
            default_customer_group=int(os.getenv("SAP_CUSTOMER_GROUP", "100")),
            bp_series=int(os.getenv("SAP_BP_SERIES", "-1")),
        )

class SyncConfig(BaseModel):
    """Sync configuration."""
    batch_size: int = 50
    max_retries: int = 3
    retry_delay: int = 5
    failed_records_path: Path = Path("failed_records.json")

class Config(BaseModel):
    """Application configuration."""
    shopify: ShopifyConfig
    sap: SAPConfig
    sync: SyncConfig = SyncConfig()
    
    @classmethod
    def from_env(cls) -> "Config":
        """Create configuration from environment variables."""
        return cls(
            shopify=ShopifyConfig(
                shop_url=os.getenv("SHOPIFY_SHOP_URL"),
                access_token=os.getenv("SHOPIFY_ACCESS_TOKEN")
            ),
            sap=SAPConfig.from_env(),
            sync=SyncConfig(
                batch_size=int(os.getenv("SYNC_BATCH_SIZE", "50")),
                max_retries=int(os.getenv("SYNC_MAX_RETRIES", "3")),
                retry_delay=int(os.getenv("SYNC_RETRY_DELAY", "5")),
                failed_records_path=Path(os.getenv("SYNC_FAILED_RECORDS_PATH", "failed_records.json"))
            )
        )
