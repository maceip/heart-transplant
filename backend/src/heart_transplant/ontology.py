from __future__ import annotations

from enum import Enum
from typing import Iterable


class FEBlock(str, Enum):
    IDENTITY_UI = "Identity UI"
    STATE_MGMT = "State Management"
    CORE_RENDERING = "Core Rendering"
    INTERACTION_DESIGN = "Interaction Design"
    ASSET_DELIVERY = "Asset Delivery"
    GLOBAL_INTERFACE = "Global Interface"
    EDGE_SUPPORT = "Edge Support"
    EXPERIMENTATION = "Experimentation"
    USER_OBSERVABILITY = "User Observability"
    ERROR_BOUNDARIES = "Error Boundaries"
    PERSISTENCE_STRATEGY = "Persistence Strategy"
    VISUAL_SYSTEMS = "Visual Systems"


class BEBlock(str, Enum):
    ACCESS_CONTROL = "Access Control"
    SYSTEM_TELEMETRY = "System Telemetry"
    DATA_PERSISTENCE = "Data Persistence"
    BACKGROUND_PROCESSING = "Background Processing"
    TRAFFIC_CONTROL = "Traffic Control"
    NETWORK_EDGE = "Network Edge"
    SEARCH_ARCH = "Search Architecture"
    SECURITY_OPS = "Security Ops"
    CONNECTIVITY_LAYER = "Connectivity Layer"
    RESILIENCY = "Resiliency"
    DATA_SOVEREIGNTY = "Data Sovereignty"
    ANALYTICAL_INTEL = "Analytical Intelligence"


def iter_blocks() -> Iterable[str]:
    yield from (block.value for block in FEBlock)
    yield from (block.value for block in BEBlock)

