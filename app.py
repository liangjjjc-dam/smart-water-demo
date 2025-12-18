import os
from datetime import datetime
import streamlit as st
import pandas as pd
import requests
import folium
from streamlit_folium import st_folium
from sqlalchemy import create_engine, desc, asc
from sqlalchemy.orm import sessionmaker
from models import Base, Reservoir, RealtimeData


def get_db_path():
    """获取数据库路径"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "data", "reservoirs.db")


def get_session():
    """创建数据库会话"""
    db_path = get_db_path()
    engine = create_engine(f"sqlite:///{db_path}", echo=False, future=True)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def get_reservoirs_with_latest_data(session):
    """查询所有水库及其最新的实时数据"""
    reservoirs = session.query(Reservoir).all()
    result = []
    
    for reservoir in reservoirs:
        # 获取该水库最新的实时数据
        latest_data = (
            session.query(RealtimeData)
            .filter(RealtimeData.reservoir_id == reservoir.id)
            .order_by(desc(RealtimeData.timestamp))
            .first()
        )
        result.append({
            "reservoir": reservoir,
            "latest_data": latest_data
        })
    
    return result


@st.cache_data(ttl=600)
def get_weather(lat: float, lon: float) -> dict:
    """
    获取指定经纬度的实时天气数据
    使用 Streamlit 缓存，10分钟(600秒)内相同位置不重复请求
    
    参数:
        lat: 纬度
        lon: 经度
    返回:
        dict: {"temperature": 温度, "weathercode": 天气代码} 或 {"error": "暂无数据"}
    """
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        current_weather = data.get("current_weather", {})
        
        return {
            "temperature": current_weather.get("temperature"),
            "weathercode": current_weather.get("weathercode")
        }
    except Exception:
        # 网络请求失败，返回暂无数据
        return {"error": "暂无数据"}


def check_flood_limit(reservoir, latest_data):
    """
    检查水库是否超汛限水位
    返回: (is_over_limit, over_value)
    - is_over_limit: 是否超限
    - over_value: 超限值（米），如果未超限则为 None
    """
    # 处理汛限水位为空的情况
    if reservoir.flood_limit_level is None:
        return False, None
    
    # 没有实时数据则无法判断
    if latest_data is None:
        return False, None
    
    current_level = latest_data.water_level
    flood_limit = reservoir.flood_limit_level
    
    if current_level > flood_limit:
        return True, round(current_level - flood_limit, 2)
    
    return False, None


def create_map(reservoirs_data):
    """创建 Folium 地图并添加水库标记"""
    # 创建地图，中心设在 (32.0, 111.0)，缩放级别 6
    m = folium.Map(location=[32.0, 111.0], zoom_start=6)
    
    # 遍历水库数据，添加 Marker
    for item in reservoirs_data:
        reservoir = item["reservoir"]
        latest_data = item["latest_data"]
        
        # 检查是否超汛限
        is_over_limit, over_value = check_flood_limit(reservoir, latest_data)
        
        # 获取该水库位置的天气数据
        weather = get_weather(reservoir.latitude, reservoir.longitude)
        
        # 构建弹窗内容
        if latest_data:
            popup_content = (
                f"<b>名称:</b> {reservoir.name}<br>"
                f"<b>水位:</b> {latest_data.water_level} m<br>"
                f"<b>库容:</b> {latest_data.storage} 亿m³"
            )
            if reservoir.flood_limit_level:
                popup_content += f"<br><b>汛限水位:</b> {reservoir.flood_limit_level} m"
            if is_over_limit:
                popup_content += f"<br><span style='color:red;font-weight:bold;'>⚠️ 超汛限 {over_value} m！</span>"
        else:
            popup_content = f"<b>名称:</b> {reservoir.name}<br>暂无实时数据"
        
        # 添加天气信息到弹窗
        if "error" in weather:
            popup_content += f"<br>🌡️ <b>气温:</b> {weather['error']}"
        else:
            temp = weather.get("temperature")
            if temp is not None:
                popup_content += f"<br>🌡️ <b>气温:</b> {temp} °C"
            else:
                popup_content += "<br>🌡️ <b>气温:</b> 暂无数据"
        
        # 根据是否超限设置图标颜色和样式
        if is_over_limit:
            # 超汛限：红色图标 + 感叹号
            icon = folium.Icon(color="red", icon="exclamation-triangle", prefix="fa")
            tooltip_text = f"⚠️ {reservoir.name} - 超汛限！"
        else:
            # 正常：蓝色图标
            icon = folium.Icon(color="blue", icon="tint", prefix="fa")
            tooltip_text = reservoir.name
        
        # 添加标记
        folium.Marker(
            location=[reservoir.latitude, reservoir.longitude],
            popup=folium.Popup(popup_content, max_width=300),
            tooltip=tooltip_text,
            icon=icon
        ).add_to(m)
    
    return m


def main():
    # 页面配置
    st.set_page_config(
        page_title="智慧水利监测平台 MVP",
        page_icon="💧",
        layout="wide"
    )
    
    # 标题
    st.title("💧 智慧水利监测平台 MVP")
    
    # 获取数据库会话
    session = get_session()
    
    try:
        # 查询数据
        reservoirs_data = get_reservoirs_with_latest_data(session)
        reservoir_count = len(reservoirs_data)
        
        # ========== 全局超汛限报警检查 ==========
        alert_reservoirs = []
        for item in reservoirs_data:
            reservoir = item["reservoir"]
            latest_data = item["latest_data"]
            is_over_limit, over_value = check_flood_limit(reservoir, latest_data)
            if is_over_limit:
                alert_reservoirs.append({
                    "name": reservoir.name,
                    "current_level": latest_data.water_level,
                    "over_value": over_value
                })
        
        # 显示全局报警
        if alert_reservoirs:
            for alert in alert_reservoirs:
                st.error(
                    f"⚠️ 警报：【{alert['name']}】当前水位 {alert['current_level']} m，"
                    f"超汛限 {alert['over_value']} m！"
                )
        
        # 布局：左侧边栏 + 主区域
        with st.sidebar:
            st.header("📊 统计数据")
            st.metric(label="当前纳管水库数量", value=f"{reservoir_count} 座")
            
            st.divider()
            st.subheader("水库列表")
            for item in reservoirs_data:
                reservoir = item["reservoir"]
                latest_data = item["latest_data"]
                with st.expander(f"🏞️ {reservoir.name}"):
                    st.write(f"**经度:** {reservoir.longitude}")
                    st.write(f"**纬度:** {reservoir.latitude}")
                    if reservoir.flood_limit_level:
                        st.write(f"**汛限水位:** {reservoir.flood_limit_level} m")
                    if reservoir.design_capacity:
                        st.write(f"**设计库容:** {reservoir.design_capacity} 亿m³")
                    if latest_data:
                        st.write(f"**当前水位:** {latest_data.water_level} m")
                        st.write(f"**当前库容:** {latest_data.storage} 亿m³")
            
            # 实时水位上报表单
            st.divider()
            st.subheader("📝 实时水位上报")
            
            # 构建水库名称到ID的映射
            reservoir_options = {item["reservoir"].name: item["reservoir"].id for item in reservoirs_data}
            
            # 下拉菜单：选择水库（放在表单外面，以便复用）
            selected_reservoir_name = st.selectbox(
                "选择水库",
                options=list(reservoir_options.keys()),
                key="reservoir_selector"
            )
            
            with st.form(key="water_level_form"):
                # 数字输入框：当前水位
                water_level_input = st.number_input(
                    "当前水位 (m)",
                    min_value=0.0,
                    max_value=500.0,
                    value=100.0,
                    step=0.1,
                    format="%.1f"
                )
                
                # 数字输入框：当前库容
                storage_input = st.number_input(
                    "当前库容 (亿m³)",
                    min_value=0.0,
                    max_value=1000.0,
                    value=50.0,
                    step=0.1,
                    format="%.1f"
                )
                
                # 提交按钮
                submit_button = st.form_submit_button("更新数据")
                
                if submit_button:
                    if selected_reservoir_name and reservoir_options:
                        # 获取选中水库的ID
                        selected_reservoir_id = reservoir_options[selected_reservoir_name]
                        
                        # 插入新的实时数据记录
                        new_data = RealtimeData(
                            reservoir_id=selected_reservoir_id,
                            timestamp=datetime.utcnow(),
                            water_level=water_level_input,
                            storage=storage_input
                        )
                        session.add(new_data)
                        session.commit()
                        
                        st.success("✅ 更新成功！")
                        # 刷新页面以显示最新数据
                        st.rerun()
                    else:
                        st.error("❌ 请先选择水库！")
        
        # 主区域：地图
        st.subheader("🗺️ 水库分布地图")
        
        if reservoir_count > 0:
            # 创建并渲染地图
            folium_map = create_map(reservoirs_data)
            st_folium(folium_map, width=None, height=600, use_container_width=True)
            
            # 水位过程线图表
            st.divider()
            st.subheader(f"📈 {selected_reservoir_name} - 水位过程线")
            
            # 获取选中水库的历史数据
            if selected_reservoir_name and reservoir_options:
                selected_id = reservoir_options[selected_reservoir_name]
                
                # 查询该水库所有历史记录，按时间升序排序
                history_data = (
                    session.query(RealtimeData)
                    .filter(RealtimeData.reservoir_id == selected_id)
                    .order_by(asc(RealtimeData.timestamp))
                    .all()
                )
                
                if history_data:
                    # 使用 pandas 整理数据
                    df = pd.DataFrame([
                        {
                            "时间": record.timestamp,
                            "水位 (m)": record.water_level,
                            "库容 (亿m³)": record.storage
                        }
                        for record in history_data
                    ])
                    df.set_index("时间", inplace=True)
                    
                    # 使用两列布局显示图表
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("#### 📊 水位变化过程线")
                        st.line_chart(df[["水位 (m)"]], use_container_width=True)
                    
                    with col2:
                        st.markdown("#### 📊 库容变化过程线")
                        st.area_chart(df[["库容 (亿m³)"]], use_container_width=True)
                    
                    # 显示历史数据表格
                    with st.expander("📋 查看历史数据明细"):
                        st.dataframe(df.reset_index(), use_container_width=True)
                    
                    # ========== 水情分析简报 ==========
                    st.divider()
                    st.subheader("📋 水情分析简报")
                    
                    # 重置索引以便访问时间列
                    df_report = df.reset_index()
                    
                    # 计算统计指标
                    max_water_level = df_report["水位 (m)"].max()
                    min_water_level = df_report["水位 (m)"].min()
                    
                    # 最新一条数据
                    latest_record = df_report.iloc[-1]
                    latest_time = latest_record["时间"]
                    latest_water_level = latest_record["水位 (m)"]
                    latest_storage = latest_record["库容 (亿m³)"]
                    
                    # 计算水位变化趋势（处理数据不足2条的边界情况）
                    if len(df_report) >= 2:
                        previous_water_level = df_report.iloc[-2]["水位 (m)"]
                        change_value = latest_water_level - previous_water_level
                        
                        if change_value > 0:
                            trend = "📈 上涨"
                            change_text = f"+{change_value:.1f}"
                        elif change_value < 0:
                            trend = "📉 下落"
                            change_text = f"{change_value:.1f}"
                        else:
                            trend = "➖ 持平"
                            change_text = "0.0"
                    else:
                        trend = "➖ 无法判断"
                        change_text = "N/A（数据不足）"
                    
                    # 格式化时间显示
                    if isinstance(latest_time, datetime):
                        formatted_time = latest_time.strftime("%Y-%m-%d %H:%M:%S")
                    else:
                        formatted_time = str(latest_time)
                    
                    # 生成文本报告
                    report_markdown = f"""
### 【{selected_reservoir_name}】水情简报
- **截止时间**: {formatted_time}
- **当前运行水位**: {latest_water_level:.1f} m
- **历史最高**: {max_water_level:.1f} m
- **历史最低**: {min_water_level:.1f} m
- **近期水势**: {trend} (较上期变化 {change_text} m)
- **当前库容**: {latest_storage:.1f} 亿m³
"""
                    st.markdown(report_markdown)
                    
                    # 数据导出功能
                    st.divider()
                    
                    # 准备导出的 CSV 数据
                    csv_data = df_report.to_csv(index=False, encoding="utf-8-sig")
                    
                    st.download_button(
                        label="📥 下载历史数据 (CSV)",
                        data=csv_data,
                        file_name=f"{selected_reservoir_name}_history.csv",
                        mime="text/csv",
                        help=f"下载 {selected_reservoir_name} 的所有历史水位数据"
                    )
                else:
                    st.info("ℹ️ 暂无历史数据")
            else:
                st.warning("⚠️ 请在侧边栏选择一个水库")
        else:
            st.warning("⚠️ 数据库中暂无水库数据，请先运行 init_db.py 初始化数据。")
    
    finally:
        # 确保正确关闭数据库会话
        session.close()


if __name__ == "__main__":
    main()

