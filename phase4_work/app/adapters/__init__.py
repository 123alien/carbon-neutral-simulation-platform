from .base import DataSourceAdapter, AdapterRegistry, ExtractedRecord
from .implementations import FileAdapter, RestApiAdapter, MqttAdapter, ManualAdapter

AdapterRegistry.register("FILE", FileAdapter)
AdapterRegistry.register("REST_API", RestApiAdapter)
AdapterRegistry.register("MQTT", MqttAdapter)
AdapterRegistry.register("THIRD_PARTY", RestApiAdapter)
AdapterRegistry.register("MANUAL", ManualAdapter)
