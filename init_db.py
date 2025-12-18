import os
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Reservoir, RealtimeData


def get_db_url():
    """
    获取数据库连接 URL
    优先从 Streamlit secrets 读取，如果不在 Streamlit 环境则尝试环境变量
    """
    # 方式1：尝试从 Streamlit secrets 读取
    try:
        import streamlit as st
        if hasattr(st, 'secrets') and "db_url" in st.secrets:
            return st.secrets["db_url"]
    except Exception:
        pass
    
    # 方式2：尝试从环境变量读取
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        return db_url
    
    # 方式3：都没有则提示用户配置
    print("=" * 60)
    print("❌ 错误：未找到数据库连接配置！")
    print("请选择以下方式之一进行配置：")
    print("")
    print("方式1 - Streamlit secrets (推荐)：")
    print("  创建 .streamlit/secrets.toml 文件，添加：")
    print('  db_url = "postgresql://user:pass@host:port/dbname"')
    print("")
    print("方式2 - 环境变量：")
    print('  set DATABASE_URL=postgresql://user:pass@host:port/dbname')
    print("=" * 60)
    raise SystemExit(1)


def init_database():
    db_url = get_db_url()
    print(f">>> 连接数据库...")
    
    # 创建数据库引擎
    engine = create_engine(db_url, echo=False, future=True)
    
    # 1. 建表
    Base.metadata.create_all(engine)
    
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    try:
        if session.query(Reservoir).count() > 0:
            print(">>> 数据库已存在数据，跳过初始化。")
            return

        print(">>> 开始初始化水库数据...")
        
        # 2. 创建水库对象
        r1 = Reservoir(name="三峡水库", longitude=111.003, latitude=30.823, flood_limit_level=145.0, design_capacity=393.0)
        r2 = Reservoir(name="丹江口水库", longitude=111.513, latitude=32.650, flood_limit_level=157.0, design_capacity=174.0)
        r3 = Reservoir(name="小浪底水库", longitude=112.465, latitude=34.916, flood_limit_level=275.0, design_capacity=126.0)
        
        session.add_all([r1, r2, r3])
        session.flush() # 关键：刷新缓冲区，让数据库生成 ID，但还不提交

        # 3. 创建实时数据 (关联刚才生成的水库ID)
        now = datetime.utcnow()
        d1 = RealtimeData(reservoir_id=r1.id, timestamp=now, water_level=160.0, storage=300.0)
        d2 = RealtimeData(reservoir_id=r2.id, timestamp=now, water_level=158.5, storage=140.0)
        d3 = RealtimeData(reservoir_id=r3.id, timestamp=now, water_level=270.0, storage=110.0)
        
        session.add_all([d1, d2, d3])
        
        session.commit() # 最终提交
        print("✅ 数据库初始化成功！（PostgreSQL）")
        
    except Exception as e:
        session.rollback()
        print(f"❌ 初始化失败: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    init_database()