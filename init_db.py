import os
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Reservoir, RealtimeData

def get_db_path():
    # 自动在当前目录下创建 data 文件夹
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "reservoirs.db")

def init_database():
    db_path = get_db_path()
    # 创建数据库引擎
    engine = create_engine(f"sqlite:///{db_path}", echo=False, future=True)
    
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
        print("✅ 数据库初始化成功！文件位于 data/reservoirs.db")
        
    except Exception as e:
        session.rollback()
        print(f"❌ 初始化失败: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    init_database()