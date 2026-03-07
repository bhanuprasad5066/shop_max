import os


class Config:
    SECRET_KEY = "dev-secret-key"
    MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "shop_max")
    RAZORPAY_KEY = os.getenv("RAZORPAY_KEY", "")
    RAZORPAY_SECRET = os.getenv("RAZORPAY_SECRET", "")