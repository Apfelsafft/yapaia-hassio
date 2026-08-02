from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    backend_cors_origins: str = "http://localhost:5173,http://localhost:8080"

    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_user: str = "navi"
    postgres_password: str = "changeme"
    postgres_db: str = "navi"

    mqtt_host: str = "mosquitto"
    mqtt_port: int = 1883

    graphhopper_url: str = "http://graphhopper:8989"
    photon_url: str = "http://photon:2322"
    tileserver_url: str = "http://tileserver:8080"

    ha_base_url: str = ""
    ha_token: str = ""

    gps_serial_port: str = ""
    gps_serial_baud: int = 9600

    secret_key: str = "change-me-in-production-use-openssl-rand-hex-32"

    # Komma-getrennte Liste von E-Mail-Adressen, die beim Backend-Start
    # automatisch zu Admins promoviert werden. Praktisch für Erst-Setup auf
    # bestehenden Installationen, wo der Auto-Admin (= erster User) nicht greift.
    admin_emails: str = ""

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "https://yapaia.cloud/api/auth/google/callback"

    tankerkonig_api_key: str = ""  # legacy – use the tankerkoenig addon settings instead
    marketplace_url: str = "http://marketplace:8100"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.backend_cors_origins.split(",") if o.strip()]


settings = Settings()
