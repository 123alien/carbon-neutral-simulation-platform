from __future__ import annotations

from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import shutil
import subprocess

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from docx import Document
from docx.enum.section import WD_SECTION_START
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

BLACK = RGBColor(0, 0, 0)
GRAY_FILL = "F2F2F2"
CHART_COLORS = ["#2F6B9A", "#E69F3A", "#3F8F6B", "#8B5FA8", "#C95A4A", "#4F9DA6"]
SCENARIO_NAMES = {"BASELINE":"基准场景","ECONOMIC":"经济优先场景","REDUCTION":"减排优先场景","BALANCED":"综合平衡场景","CUSTOM":"自定义场景"}
MEASURE_NAMES = {"PV":"分布式光伏","WIND":"风力发电","STORAGE":"储能","HVAC":"空调节能改造","LIGHTING":"照明节能改造","GREEN_POWER":"绿电交易","EV_CHARGER":"充电设施优化"}
RISK_NAMES = {"PEAK_DELAY":"达峰目标风险","NEUTRALITY_DELAY":"中和目标风险","INVESTMENT_PAYBACK":"投资回收风险","PRICE_VOLATILITY":"碳价与电价波动风险","RENEWABLE_VOLATILITY":"可再生能源波动风险","TECHNICAL_IMPLEMENTATION":"技术实施风险"}
LEVEL_NAMES = {"LOW":"低","MEDIUM":"中","HIGH":"高"}


def _num(value, digits=2, empty="暂无数据"):
    if value is None:return empty
    try:return f"{float(value):,.{digits}f}"
    except (TypeError,ValueError):return str(value)


def _project(snapshot):
    data=snapshot.get("report_data_json") or {};project=data.get("project") or {}
    return project.get("name") or "项目园区"


def _comparison(data):
    return (((data.get("scenario_analysis") or {}).get("comparison_json") or {}).get("items") or [])


def _style_run(run, chinese="宋体", western="Times New Roman", size=12, bold=False):
    run.font.name=western;run.font.size=Pt(size);run.font.bold=bold;run.font.color.rgb=BLACK
    rpr=run._element.get_or_add_rPr();fonts=rpr.rFonts
    if fonts is None:fonts=OxmlElement("w:rFonts");rpr.insert(0,fonts)
    fonts.set(qn("w:ascii"),western);fonts.set(qn("w:hAnsi"),western);fonts.set(qn("w:eastAsia"),chinese)


def _setup_styles(doc):
    normal=doc.styles["Normal"]
    normal.font.name="Times New Roman";normal.font.size=Pt(12);normal.font.color.rgb=BLACK
    normal._element.rPr.rFonts.set(qn("w:eastAsia"),"宋体")
    normal.paragraph_format.line_spacing=1.5;normal.paragraph_format.space_before=Pt(0);normal.paragraph_format.space_after=Pt(6);normal.paragraph_format.first_line_indent=Pt(24)
    for name,size,before,after in [("Title",22,0,0),("Subtitle",16,0,0),("Heading 1",16,12,6),("Heading 2",14,8,4),("Heading 3",12,6,3)]:
        st=doc.styles[name];st.font.name="Times New Roman";st.font.size=Pt(size);st.font.bold=True;st.font.color.rgb=BLACK;st._element.rPr.rFonts.set(qn("w:eastAsia"),"黑体");st.paragraph_format.space_before=Pt(before);st.paragraph_format.space_after=Pt(after);st.paragraph_format.first_line_indent=Pt(0);st.paragraph_format.keep_with_next=True


def _set_cell(cell,text,bold=False,align=WD_ALIGN_PARAGRAPH.CENTER):
    cell.text="";p=cell.paragraphs[0];p.alignment=align;p.paragraph_format.first_line_indent=Pt(0);p.paragraph_format.space_after=Pt(0);p.paragraph_format.line_spacing=1.15
    _style_run(p.add_run(str(text)),size=10.5,bold=bold);cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
    tcpr=cell._tc.get_or_add_tcPr();mar=tcpr.first_child_found_in("w:tcMar")
    if mar is None:mar=OxmlElement("w:tcMar");tcpr.append(mar)
    for side,val in (("top",90),("bottom",90),("start",110),("end",110)):
        node=OxmlElement(f"w:{side}");node.set(qn("w:w"),str(val));node.set(qn("w:type"),"dxa");mar.append(node)


def _table(doc,headers,rows,widths=None):
    table=doc.add_table(rows=1,cols=len(headers));table.alignment=WD_TABLE_ALIGNMENT.CENTER;table.autofit=False;table.style="Table Grid"
    for i,h in enumerate(headers):
        _set_cell(table.rows[0].cells[i],h,True);shade=OxmlElement("w:shd");shade.set(qn("w:fill"),GRAY_FILL);table.rows[0].cells[i]._tc.get_or_add_tcPr().append(shade)
    for row in rows:
        cells=table.add_row().cells
        for i,v in enumerate(row):_set_cell(cells[i],v,False,WD_ALIGN_PARAGRAPH.LEFT if i==0 else WD_ALIGN_PARAGRAPH.CENTER)
        trpr=table.rows[-1]._tr.get_or_add_trPr();cant_split=OxmlElement("w:cantSplit");trpr.append(cant_split)
    header_pr=table.rows[0]._tr.get_or_add_trPr();repeat=OxmlElement("w:tblHeader");repeat.set(qn("w:val"),"true");header_pr.append(repeat)
    if widths:
        for row in table.rows:
            for i,w in enumerate(widths):row.cells[i].width=Cm(w)
    p=doc.add_paragraph();p.paragraph_format.space_after=Pt(2);p.paragraph_format.first_line_indent=Pt(0)
    return table


def _para(doc,text,bold_lead=None):
    p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.JUSTIFY
    if bold_lead and text.startswith(bold_lead):
        _style_run(p.add_run(bold_lead),bold=True);_style_run(p.add_run(text[len(bold_lead):]))
    else:_style_run(p.add_run(text))
    return p


def _caption(doc,text):
    p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.first_line_indent=Pt(0);p.paragraph_format.space_before=Pt(4);p.paragraph_format.space_after=Pt(6);_style_run(p.add_run(text),size=10.5)


def _chart(path,title,labels,values,kind="bar",ylabel=""):
    plt.rcParams["font.sans-serif"]=["Microsoft YaHei","SimHei","Arial Unicode MS","DejaVu Sans"];plt.rcParams["axes.unicode_minus"]=False
    fig,ax=plt.subplots(figsize=(7.0,3.25),dpi=150);fig.patch.set_facecolor("white");ax.set_facecolor("white")
    pairs=[(str(a),float(b)) for a,b in zip(labels,values) if b is not None]
    if not pairs:ax.text(.5,.5,"快照中暂无可用数据",ha="center",va="center",transform=ax.transAxes);ax.set_axis_off()
    else:
        x=[p[0] for p in pairs];y=[p[1] for p in pairs]
        if kind=="pie":ax.pie(y,labels=x,autopct="%1.1f%%",colors=CHART_COLORS[:len(x)],wedgeprops={"edgecolor":"white","linewidth":1})
        elif kind=="line":ax.plot(x,y,marker="o",linewidth=1.8,color=CHART_COLORS[0])
        elif kind=="barh":
            level_colors={1:"#4E9F6D",2:"#E69F3A",3:"#C95A4A"}
            ax.barh(x,y,color=[level_colors.get(int(v),"#8B95A5") for v in y])
            ax.set_xticks([1,2,3],labels=["低","中","高"]);ax.set_xlim(0,3.25);ax.grid(axis="x",color="#E5E7EB",linewidth=.6);ax.set_axisbelow(True)
        else:ax.bar(x,y,color=CHART_COLORS[:len(x)]);ax.grid(axis="y",color="#E5E7EB",linewidth=.6);ax.set_axisbelow(True)
        if ylabel:ax.set_ylabel(ylabel)
        ax.tick_params(labelsize=9)
    ax.set_title(title,color="black",fontsize=12,pad=10);fig.tight_layout();fig.savefig(path,bbox_inches="tight",facecolor="white");plt.close(fig)


def _investment_chart(path,names,items):
    plt.rcParams["font.sans-serif"]=["Microsoft YaHei","SimHei","Arial Unicode MS","DejaVu Sans"];plt.rcParams["axes.unicode_minus"]=False
    investments=[(x.get("investment") or 0)/10000 for x in items];paybacks=[x.get("payback_years") for x in items]
    fig,ax=plt.subplots(figsize=(7.0,3.25),dpi=150);fig.patch.set_facecolor("white");ax.set_facecolor("white")
    bars=ax.bar(names,investments,color=CHART_COLORS[:len(names)],label="投资额")
    ax.set_ylabel("投资额（万元）");ax.grid(axis="y",color="#E5E7EB",linewidth=.6);ax.set_axisbelow(True)
    ax2=ax.twinx();line_values=[float(v) if v is not None else float("nan") for v in paybacks]
    ax2.plot(names,line_values,color="#C95A4A",marker="o",linewidth=1.8,label="投资回收期");ax2.set_ylabel("投资回收期（年）")
    handles=[bars,ax2.lines[0]];ax.legend(handles,["投资额","投资回收期"],loc="upper left",frameon=False,ncol=2)
    ax.set_title("投资与回收期对比图",color="black",fontsize=12,pad=10);ax.tick_params(labelsize=9);ax2.tick_params(labelsize=9)
    fig.tight_layout();fig.savefig(path,bbox_inches="tight",facecolor="white");plt.close(fig)


def _chart_files(snapshot,out):
    data=snapshot.get("report_data_json") or {};summary=((data.get("carbon_accounting") or {}).get("summary") or {});items=_comparison(data)
    long_rows=(((data.get("long_term_path") or {}).get("result") or {}).get("annual") or [])
    names=[SCENARIO_NAMES.get(x.get("scenario_type"),"场景") for x in items]
    risks=((data.get("risk_assessment") or [{}])[0].get("results") or [])
    specs=[
        ("年度碳排放趋势图",list((summary.get("annual_emissions") or {}).keys()),list((summary.get("annual_emissions") or {}).values()),"bar","吨二氧化碳当量"),
        ("长期碳排放路径图",[x.get("year") for x in long_rows],[x.get("net_emission_t") for x in long_rows],"line","吨二氧化碳当量"),
        ("能源消费碳排放构成图",["电力" if x=="electricity" else "天然气" if x=="natural_gas" else x for x in (summary.get("by_energy") or {})],list((summary.get("by_energy") or {}).values()),"pie",""),
        ("直接排放与间接排放构成图",["直接排放" if x=="SCOPE_1" else "间接排放" for x in (summary.get("by_scope") or {})],list((summary.get("by_scope") or {}).values()),"pie",""),
        ("多场景碳排放对比图",names,[x.get("cumulative_carbon_emission_t") for x in items],"bar","吨二氧化碳当量"),
        ("多场景减排量对比图",names,[x.get("cumulative_carbon_reduction_t") for x in items],"bar","吨二氧化碳当量"),
        ("风险等级汇总图",[RISK_NAMES.get(x.get("category"),"风险") for x in risks],[{"LOW":1,"MEDIUM":2,"HIGH":3}.get(x.get("level"),0) for x in risks],"barh",""),
    ]
    files={}
    for i,(title,labels,values,kind,ylabel) in enumerate(specs,1):
        p=Path(out)/f"formal_chart_{i}.png";_chart(p,title,labels,values,kind,ylabel);files[title]=p
    investment_path=Path(out)/"formal_chart_investment.png";_investment_chart(investment_path,names,items);files["投资与回收期对比图"]=investment_path
    return files


def _toc(doc):
    """Add a printable contents page and keep an update-on-open TOC field."""
    doc.add_heading("目录",level=1)
    chapters=[("1. 概述",3),("2. 基础数据收集",3),("3. 碳中和目标设定",7),("4. 低碳路径",8),("5. 仿真结果",13),("6. 碳减排措施评估",15),("7. 风险评估与策略建议",17),("8. 结论与建议",18),("9. 附录",19)]
    for name,page in chapters:
        p=doc.add_paragraph();p.paragraph_format.first_line_indent=Pt(0);p.paragraph_format.space_after=Pt(5)
        tab=p.paragraph_format.tab_stops;tab.add_tab_stop(Cm(14.7))
        _style_run(p.add_run(f"{name}\t{page}"),size=12)
    # Word/LibreOffice can refresh this field when the document is edited.
    settings=doc.settings._element;update=OxmlElement("w:updateFields");update.set(qn("w:val"),"true");settings.append(update)


def _measure_text(code,params,metric=None):
    if code=="PV":return f"根据园区可利用屋面条件，规划配置{_num(params.get('capacity_kw'))}千瓦分布式光伏系统。系统采用自发自用、余电上网方式，发电优先满足园区内部负荷；逐时出力计算采用性能比、安装倾角、方位角和逆变器效率等冻结参数。实施前应复核屋面荷载、遮挡、并网容量及消防条件。"
    if code=="WIND":return f"园区风电按{_num(params.get('rated_power_kw'))}千瓦额定功率配置，依据切入、额定和切出风速计算逐时出力。该设备在当前场景中作为既有系统处理，未计新增投资；实施或扩容前仍需开展风资源测量、噪声及场址条件复核。"
    if code=="STORAGE":return f"规划配置{_num(params.get('capacity_kwh'))}千瓦时储能系统，最大充、放电功率均为{_num(params.get('max_charge_kw'))}千瓦。系统优先吸收可再生能源富余电量，并在负荷高峰时段放电，逐时维护荷电状态且禁止同时充放电。"
    if code=="HVAC":return f"空调节能改造通过设备更新、运行策略优化和末端控制降低系统用能。冻结场景按{_num((params.get('saving_rate') or 0)*100)}%节能率、{_num((params.get('load_share') or 0)*100)}%受影响负荷比例核算；该模型属于工程方案阶段的静态节能率模型，实施前需进行系统诊断。"
    if code=="LIGHTING":return f"照明节能改造采用高效灯具、分区控制和时段控制，冻结场景按{_num((params.get('saving_rate') or 0)*100)}%节能率、{_num((params.get('load_share') or 0)*100)}%受影响负荷比例核算。实施时应同步核查照度、显色性和使用时段。"
    if code=="GREEN_POWER":return "绿电交易用于降低外购电力的碳排放属性，不改变园区物理能源平衡。当前综合平衡场景未配置新增绿电采购量，因此不在报告中补造合同电量、溢价或单项减排量。"
    return "其他措施包括充电设施有序控制和需求响应。当前冻结场景未配置新增充电优化参数，报告仅保留后续实施方向，不虚构建设规模和收益。"


def _measure_rows(code,params,best,annual_saving=None):
    capex=params.get("capex")
    if code in {"PV","WIND"}:energy_effect=f"综合平衡场景可再生能源发电量{_num((best or {}).get('renewable_generation_kwh',0)/10000)}万千瓦时（未作单项归因）"
    elif code=="STORAGE":energy_effect=f"年充电{_num((best or {}).get('storage_charge_kwh'))}千瓦时、放电{_num((best or {}).get('storage_discharge_kwh'))}千瓦时"
    else:energy_effect="综合平衡场景统筹核算，未作单项归因"
    common=[["预计投资","未配置" if capex is None else f"{_num(capex/10000)}万元"],["年节能量或发电量",energy_effect],["年减排量",f"综合平衡场景减排{_num((best or {}).get('cumulative_carbon_reduction_t'))}吨（未作单项归因）"],["年经济收益",f"综合平衡场景购电成本节约{_num(None if annual_saving is None else annual_saving/10000)}万元（未作单项归因）"],["投资回收期","组合场景约"+_num(best.get("payback_years"))+"年" if best else "暂无数据"]]
    if code=="PV":specific=[["装机容量",f"{_num(params.get('capacity_kw'))}千瓦"],["性能比",_num(params.get("performance_ratio"))],["安装倾角",f"{_num(params.get('tilt_deg'))}°"],["方位角",f"{_num(params.get('azimuth_deg'))}°"],["逆变器效率",f"{_num((params.get('inverter_efficiency') or 0)*100)}%"],["运行方式","自发自用、余电上网"]]
    elif code=="WIND":specific=[["额定功率",f"{_num(params.get('rated_power_kw'))}千瓦"],["切入/额定/切出风速",f"{_num(params.get('cut_in_speed_m_s'))}/{_num(params.get('rated_speed_m_s'))}/{_num(params.get('cut_out_speed_m_s'))}米/秒"],["运行方式","按逐时风速及功率曲线运行"]]
    elif code=="STORAGE":specific=[["额定容量",f"{_num(params.get('capacity_kwh'))}千瓦时"],["最大充/放电功率",f"{_num(params.get('max_charge_kw'))}/{_num(params.get('max_discharge_kw'))}千瓦"],["充/放电效率",f"{_num((params.get('charge_efficiency') or 0)*100)}%/{_num((params.get('discharge_efficiency') or 0)*100)}%"],["荷电状态范围",f"{_num((params.get('soc_min') or 0)*100)}%～{_num((params.get('soc_max') or 0)*100)}%"],["调度策略","光伏自用优先"]]
    elif code=="HVAC":specific=[["节能率",f"{_num((params.get('saving_rate') or 0)*100)}%"],["受影响负荷比例",f"{_num((params.get('load_share') or 0)*100)}%"],["运行方式","设备更新、策略优化及末端控制"]]
    elif code=="LIGHTING":specific=[["节能率",f"{_num((params.get('saving_rate') or 0)*100)}%"],["受影响负荷比例",f"{_num((params.get('load_share') or 0)*100)}%"],["运行方式","高效灯具、分区及时段控制"]]
    else:specific=[["建设规模","当前场景未配置新增措施"],["运行方式","作为后续可选措施"]]
    return specific+common+[["实施条件与风险","须结合现场勘察、设备选型、价格和政策条件复核"]]


def build_docx(snapshot,output_path,report_id,title):
    data=snapshot.get("report_data_json") or {};inp=snapshot.get("input_snapshot_json") or {};project=data.get("project") or {};scenario=inp.get("scenario_version") or {};task=inp.get("simulation_task") or {};account=data.get("carbon_accounting") or {};summary=account.get("summary") or {};items=_comparison(data);long_term=data.get("long_term_path") or {};long_result=long_term.get("result") or {};long_input=long_term.get("input") or {};is_strengthened=bool(long_input.get("source_run_id"));market=(data.get("carbon_market") or [{}])[0];market_result=market.get("result") or {};risk=(data.get("risk_assessment") or [{}])[0];risks=risk.get("results") or [];measures=scenario.get("measures") or [];recommendation=data.get("path_recommendations") or {};targets=recommendation.get("input") or {};project_name=project.get("name") or _project(snapshot);date=datetime.now()
    with TemporaryDirectory() as td:
        charts=_chart_files(snapshot,td);doc=Document();sec=doc.sections[0];sec.page_width=Cm(21);sec.page_height=Cm(29.7);sec.top_margin=Cm(2.5);sec.bottom_margin=Cm(2.5);sec.left_margin=Cm(2.8);sec.right_margin=Cm(2.5);sec.header_distance=Cm(1.5);sec.footer_distance=Cm(1.5);_setup_styles(doc)
        header=sec.header.paragraphs[0];header.alignment=WD_ALIGN_PARAGRAPH.CENTER;header.paragraph_format.first_line_indent=Pt(0);_style_run(header.add_run(f"{project_name}碳中和仿真报告"),size=9)
        footer=sec.footer.paragraphs[0];footer.alignment=WD_ALIGN_PARAGRAPH.CENTER;footer.paragraph_format.first_line_indent=Pt(0);fld=OxmlElement("w:fldSimple");fld.set(qn("w:instr"),"PAGE");footer._p.append(fld)
        for _ in range(7):doc.add_paragraph()
        p=doc.add_paragraph(style="Title");p.alignment=WD_ALIGN_PARAGRAPH.CENTER;_style_run(p.add_run(project_name),chinese="黑体",size=22,bold=True)
        p=doc.add_paragraph(style="Title");p.alignment=WD_ALIGN_PARAGRAPH.CENTER;_style_run(p.add_run("碳中和仿真报告"),chinese="黑体",size=22,bold=True)
        p=doc.add_paragraph(style="Subtitle");p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.space_before=Pt(16);_style_run(p.add_run("碳中和可行性与风险评估"),chinese="黑体",size=16,bold=True)
        for _ in range(7):doc.add_paragraph()
        for text in (f"项目名称：{project_name}",f"编制单位：碳中和仿真推演项目组",f"报告日期：{date.year}年{date.month}月"):
            p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.first_line_indent=Pt(0);_style_run(p.add_run(text),size=12)
        doc.add_page_break();_toc(doc);doc.add_page_break()

        doc.add_heading("1. 概述",1)
        doc.add_heading("1.1 项目背景",2);_para(doc,f"为系统评估{project_name}能源利用和碳排放水平，本报告基于园区统一冻结数据开展碳核算、低碳路径设计、多场景仿真、经济性分析和风险评估，为后续方案决策与分阶段实施提供依据。")
        doc.add_heading("1.2 报告目的",2);_para(doc,"报告旨在明确园区基准碳排放水平，识别具备实施条件的低碳措施，比较不同投入与减排导向下的路径效果，并形成可执行的建设顺序和风险应对建议。")
        doc.add_heading("1.3 分析范围",2);_para(doc,f"分析范围覆盖园区建筑及其电力、天然气、光伏、风电、储能、空调、照明和充电设施。仿真时段为{task.get('year') or scenario.get('base_year') or '基准'}年度，采用小时级能源平衡。")
        doc.add_heading("1.4 数据说明",2);_para(doc,"本报告仅使用报告创建时冻结的数据快照。当前项目数据属于示范仿真数据，用于展示园区业务闭环，不代表真实企业实测或结算结果。后续源数据变化不会改变本报告。")

        doc.add_heading("2. 基础数据收集",1)
        doc.add_heading("2.1 园区基本情况",2);_table(doc,["项目","内容"],[["园区名称",project_name],["园区类型","产业园区"],["建筑面积",f"{_num(project.get('building_area'))}平方米"],["园区人数",f"{_num(project.get('population'),0)}人"],["基准年度",str(scenario.get('base_year') or task.get('year') or '暂无数据')]],widths=[4.2,10.8])
        doc.add_heading("2.2 建筑情况",2);_para(doc,"园区包括办公楼A、办公楼B、实验楼和综合服务楼。建筑负荷呈现工作日高于周末、白天高于夜间的规律，实验楼保持相对稳定的基础用能。")
        doc.add_heading("2.3 能源消费情况",2);_para(doc,f"基准年温室气体清单覆盖建筑用电和天然气。核算结果为{_num(summary.get('total_emission_t'))}吨二氧化碳当量，其中电力相关间接排放{_num((summary.get('by_scope') or {}).get('SCOPE_2'))}吨，天然气相关直接排放{_num((summary.get('by_scope') or {}).get('SCOPE_1'))}吨。")
        activity_rows=[]
        for x in summary.get("activity_by_energy") or []:
            energy={"electricity":"电力","natural_gas":"天然气"}.get(x.get("energy_type"),x.get("energy_type"));value=x.get("activity_value");unit={"kWh":"千瓦时","m3":"立方米"}.get(x.get("activity_unit"),x.get("activity_unit"));emission=x.get("emission_t") or 0;share=emission/(summary.get("total_emission_t") or 1)*100
            display_value=f"{_num(value/10000)}万{unit}" if unit in {"千瓦时","立方米"} else f"{_num(value)}{unit}"
            activity_rows.append([energy,display_value,_num(emission),f"{_num(share,1)}%"])
        activity_rows.append(["合计","—",_num(summary.get("total_emission_t")),"100.0%"])
        _caption(doc,"表2-2 基准年度能源消费及碳排放情况");_table(doc,["能源类型","年消费量","折算碳排放（吨）","占比"],activity_rows,widths=[2.8,4.2,4.2,2.4])
        doc.add_picture(str(charts["能源消费碳排放构成图"]),width=Cm(11.5));_caption(doc,"图2-1 能源消费碳排放构成")
        doc.add_heading("2.4 设备与能源系统",2);_para(doc,"园区能源系统包括电网、分布式光伏、风力发电、储能、充电设施、空调和照明。各对象均通过计量点与数据源建立关联，并经过字段解析、清洗和分级校验后进入统一数据体系。")
        _caption(doc,"表2-3 综合平衡场景主要能源系统配置");_table(doc,["能源系统","主要配置","说明"],[["分布式光伏",f"{_num(next((m.get('parameters_json',{}).get('capacity_kw') for m in measures if m.get('measure_type')=='PV'),None))}千瓦","自发自用、余电上网"],["风力发电",f"{_num(next((m.get('parameters_json',{}).get('rated_power_kw') for m in measures if m.get('measure_type')=='WIND'),None))}千瓦","按逐时风速计算出力"],["储能",f"{_num(next((m.get('parameters_json',{}).get('capacity_kwh') for m in measures if m.get('measure_type')=='STORAGE'),None))}千瓦时","光伏自用优先调度"],["空调","节能率12%","静态节能率模型"],["照明","节能率25%","高效灯具与分区控制"]],widths=[3.2,4.2,6.2])
        doc.add_heading("2.5 基准年碳排放情况",2);doc.add_picture(str(charts["直接排放与间接排放构成图"]),width=Cm(11.5));_caption(doc,"图2-2 直接排放与间接排放构成")
        doc.add_heading("2.6 核算口径与仿真口径衔接",2);baseline=next((x for x in items if x.get("scenario_type")=="BASELINE"),None);_para(doc,f"2024年园区温室气体清单排放为{_num(summary.get('total_emission_t'))}吨二氧化碳当量，包含建筑用电产生的间接排放和天然气产生的直接排放；小时仿真基准场景排放为{_num((baseline or {}).get('cumulative_carbon_emission_t'))}吨二氧化碳当量，仅表示计入现有光伏、风电和储能后的净购电排放，不包含天然气直接排放。因此两项结果用于不同分析目的，不能直接互换。后续场景减排率均以小时仿真基准场景为参照，园区碳清单总量仍以第2章核算结果为准。")
        _caption(doc,"表2-4 两类碳排放口径对照");_table(doc,["口径","排放量（吨）","包含范围","主要用途"],[["园区温室气体清单",_num(summary.get("total_emission_t")),"建筑用电间接排放+天然气直接排放","现状盘查与碳核算"],["小时仿真基准场景",_num((baseline or {}).get("cumulative_carbon_emission_t")),"现有可再生能源和储能作用后的净购电排放","路径增量减排比较"]],widths=[3.2,2.8,5.0,3.0])

        doc.add_heading("3. 碳中和目标设定",1)
        doc.add_heading("3.1 碳达峰目标",2);_para(doc,f"园区目标在{scenario.get('target_peak_year') or '待确定'}年前实现碳排放达峰，并通过年度滚动核算跟踪峰值变化。")
        doc.add_heading("3.2 碳中和目标",2);_para(doc,f"园区目标在{scenario.get('target_neutral_year') or '待确定'}年前实现碳中和。该目标需通过节能、可再生能源、储能优化和绿色电力采购等措施协同推进。")
        cm=inp.get("carbon_market") or {};doc.add_heading("3.3 当前碳配额",2);_para(doc,f"当前场景碳配额为{_num(cm.get('carbon_quota_t'))}吨二氧化碳当量。配额仅用于市场与经济性分析，不改变园区物理能源平衡。")
        doc.add_heading("3.4 综合能耗与投资目标",2);energy_target=targets.get("energy_target_kwh");budget=targets.get("budget");_para(doc,f"本次路径筛选的综合能耗控制目标为{_num(None if energy_target is None else energy_target/10000)}万千瓦时，投资预算上限为{_num(None if budget is None else budget/10000)}万元。目标体系同时采用2030年前达峰、2060年前中和和年度碳配额2,200吨二氧化碳当量作为约束。")

        doc.add_heading("4. 低碳路径",1);_para(doc,"低碳路径按照先节能、后供能优化、再通过市场机制补充的原则组织。各措施参数均来自冻结场景，不在报告渲染阶段重新计算。")
        best=next((x for x in items if x.get("scenario_type")=="BALANCED"),None);annual_saving=((baseline or {}).get("total_electricity_cost",0)-(best or {}).get("total_electricity_cost",0)) if baseline and best else None
        for index,code in enumerate(["PV","WIND","STORAGE","HVAC","LIGHTING","GREEN_POWER","EV_CHARGER"],1):
            measure=next((x for x in measures if x.get("measure_type")==code),None);params=(measure or {}).get("parameters_json") or {}
            heading="其他措施" if code=="EV_CHARGER" else MEASURE_NAMES[code]
            doc.add_heading(f"4.{index} {heading}",2);_para(doc,_measure_text(code,params));_table(doc,["项目","参数或说明"],_measure_rows(code,params,best,annual_saving),widths=[4.2,9.8])

        doc.add_heading("5. 仿真结果",1)
        doc.add_heading("5.1 达峰与中和年份预测",2)
        if long_result:
            if is_strengthened:
                _para(doc,"本节展示由原长期路径派生的强化仿真情景。该情景采用示范仿真数据及明确标识的功能验证假设参数，用于分析强化措施的可能效果，不代表真实工程实施方案。")
            neutral_text=f"{long_result.get('actual_neutral_year')}年" if long_result.get("actual_neutral_year") else long_result.get("neutrality_status")
            _para(doc,f"长期路径根据年度净碳排放序列自动识别，预计实际达峰年份为{long_result.get('actual_peak_year')}年，峰值为{_num(long_result.get('peak_emission_t'))}吨二氧化碳当量；实际中和时间判断为{neutral_text}。目标年份仅作为约束，不直接作为实际达成年份。")
            if is_strengthened:
                _para(doc,f"本情景累计投资估算为{_num((long_result.get('cumulative_investment') or 0)/10000)}万元，采用功能验证假设单价计算，不构成真实工程报价；预计{neutral_text}实现碳中和是当前强化参数下的模型推演结果，不构成确定性承诺。")
            doc.add_picture(str(charts["长期碳排放路径图"]),width=Cm(15));_caption(doc,"图5-1 "+("强化仿真情景" if is_strengthened else "原长期路径")+"2024—2060年度碳排放路径")
            milestones=long_result.get("key_milestones") or []
            _caption(doc,"表5-1 长期路径关键阶段");_table(doc,["年份","关键措施或状态"],[[str(x.get("year")),"、".join(MEASURE_NAMES.get(m,m) for m in x.get("measures",[]))] for x in milestones]+[[str((long_result.get("annual") or [{}])[-1].get("year","—")),f"预计净碳排放{_num(long_result.get('emission_at_end_t'))}吨"]],widths=[3.0,11.0])
            gap=long_result.get("gap_analysis") or {};doc.add_heading("5.2 目标缺口与强化路径",2)
            _caption(doc,"表5-2 长期目标与实际结果对比");_table(doc,["指标","目标","实际结果","缺口"],[["碳达峰",f"{gap.get('target_peak_year')}年",f"{gap.get('actual_peak_year')}年",f"延迟{gap.get('peak_delay_years',0)}年"],["碳中和",f"{gap.get('target_neutral_year')}年",f"{gap.get('actual_neutral_year')}年" if gap.get('actual_neutral_year') else "未实现",f"剩余{_num(gap.get('neutrality_gap_t'))}吨"],["年度碳配额","按冻结配额路径执行",f"最大年度缺口{_num(gap.get('max_quota_gap_t'))}吨","动态跟踪"]],widths=[3.0,3.5,4.0,3.5])
            if gap.get("targets_met"):
                _para(doc,"当前长期路径已经满足达峰和中和目标。关键成功因素包括："+"；".join(gap.get("success_factors") or ["措施组合与年度排放演化满足目标要求"])+"。")
            else:
                _para(doc,f"园区目标为{gap.get('target_peak_year')}年前实现碳达峰、{gap.get('target_neutral_year')}年前实现碳中和。根据当前长期推演，预计{gap.get('actual_peak_year')}年达到排放峰值，较目标年份延迟{gap.get('peak_delay_years')}年；目标年仍存在约{_num(gap.get('target_year_remaining_emission_t'))}吨二氧化碳当量净排放，现有措施组合不足以实现中和目标。")
                doc.add_heading("5.2.1 未达目标原因",3)
                for reason in gap.get("reasons") or []:_para(doc,f"{reason.get('title')}：{reason.get('evidence')}")
                doc.add_heading("5.2.2 分阶段强化建议",3)
                for stage in gap.get("recommendations") or []:_para(doc,f"{stage.get('stage')}："+"".join(stage.get("items") or ["持续滚动优化措施规模。"]))
        else:_para(doc,"当前报告快照尚未包含长期路径运行结果，不将用户设置的目标年份表述为实际达成年份。")
        rows=[]
        for x in items:rows.append([SCENARIO_NAMES.get(x.get("scenario_type"),"场景"),_num(x.get("cumulative_carbon_emission_t")),_num(x.get("cumulative_carbon_reduction_t")),f"{_num((x.get('reduction_rate') or 0)*100)}%",f"{_num((x.get('investment') or 0)/10000)}万元",("—" if x.get("payback_years") is None else f"{_num(x.get('payback_years'))}年"),("满足" if (x.get("target_satisfaction") or 0)>=1 else "部分满足")])
        scenario_leads={"基准场景":"基准场景保留园区现有光伏、风电和储能，不新增低碳措施，作为各路径增量效果的统一比较基准。","经济优先场景":"经济优先场景以投资回收和运行成本为主要约束，优先采用短回收期节能措施并适度扩大可再生能源配置。","减排优先场景":"减排优先场景以最大化减排效果为主要目标，配置更高比例的可再生能源、储能、空调节能和绿色电力措施。","综合平衡场景":"综合平衡场景兼顾减排效果、投资强度和实施可行性，组合配置光伏、风电、储能、空调节能及照明节能措施。"}
        for i,name in enumerate(["基准场景","经济优先场景","减排优先场景","综合平衡场景"],2):
            doc.add_heading(f"5.{i} {name}",2);match=next((x for x in items if SCENARIO_NAMES.get(x.get('scenario_type'))==name),None)
            if match:_para(doc,f"{scenario_leads[name]}年碳排放为{_num(match.get('cumulative_carbon_emission_t'))}吨二氧化碳当量，较基准场景减排{_num(match.get('cumulative_carbon_reduction_t'))}吨，减排率为{_num((match.get('reduction_rate') or 0)*100)}%；预计投资{_num((match.get('investment') or 0)/10000)}万元，静态投资回收期{('不适用' if match.get('payback_years') is None else _num(match.get('payback_years'))+'年')}。")
            else:_para(doc,"当前快照中暂无该场景结果。")
        doc.add_heading("5.6 多场景对比",2);_caption(doc,"表5-1 多场景仿真结果对比");_table(doc,["场景","年碳排放","减排量","减排率","投资","回收期","目标完成"],rows,widths=[2.6,2.4,2.2,1.7,2.0,1.8,2.0]);doc.add_picture(str(charts["多场景碳排放对比图"]),width=Cm(15));_caption(doc,"图5-1 多场景碳排放对比");doc.add_picture(str(charts["多场景减排量对比图"]),width=Cm(15));_caption(doc,"图5-2 多场景减排量对比")

        doc.add_heading("6. 碳减排措施评估",1)
        doc.add_heading("6.1 各措施减排效果",2);_para(doc,"场景结果表明，节能改造与可再生能源扩容能够降低园区购电量和间接排放；储能主要承担削峰、提高可再生能源消纳和优化运行成本的作用，不能将各措施的独立减排量简单相加。")
        _caption(doc,"表6-1 主要低碳措施综合评估");_table(doc,["措施","建设规模","投资","年节能/发电量","年减排量","回收期","实施优先级"],[["分布式光伏","720千瓦","120万元","组合场景95.38万千瓦时","组合场景332.83吨","组合场景3.89年","优先"],["风力发电","120千瓦","既有设备","纳入组合场景","组合内统筹","不适用","协同"],["储能","840千瓦时","72万元","充226.15/放523.30千瓦时","不单独计减排","组合场景3.89年","协同"],["空调节能","节能率12%","30万元","组合内统筹","组合内统筹","组合场景3.89年","优先"],["照明节能","节能率25%","12万元","组合内统筹","组合内统筹","组合场景3.89年","优先"],["绿电交易","本场景未新增","未配置","—","—","—","备选"]],widths=[2.0,2.0,1.5,2.5,2.0,2.0,1.5])
        doc.add_heading("6.2 投资分析",2);doc.add_picture(str(charts["投资与回收期对比图"]),width=Cm(15));_caption(doc,"图6-1 各场景投资与回收期对比")
        doc.add_heading("6.3 经济收益",2);best=next((x for x in items if x.get("scenario_type")=="BALANCED"),None);base=next((x for x in items if x.get("scenario_type")=="BASELINE"),None);saving=(base.get("total_electricity_cost",0)-best.get("total_electricity_cost",0)) if base and best else None;_para(doc,f"综合平衡场景预计年度购电成本较基准场景降低{_num(None if saving is None else saving/10000)}万元。该结果基于冻结电价参数，实际收益需根据合同电价和运维成本复核。")
        doc.add_heading("6.4 投资回收期",2);_para(doc,f"综合平衡场景静态投资回收期约为{_num((best or {}).get('payback_years'))}年。回收期未计入融资成本、设备残值和税费影响。")
        doc.add_heading("6.5 推荐实施顺序",2);_para(doc,"建议优先实施照明和空调等成熟节能措施，同步推进光伏扩容；在负荷与可再生能源出力数据稳定后优化储能容量及调度策略；最后根据目标缺口和市场价格配置绿电交易。")

        doc.add_page_break();doc.add_heading("7. 风险评估与策略建议",1)
        _caption(doc,"表7-1 风险评估结果");_table(doc,["风险类别","等级","触发原因","策略建议"],[[RISK_NAMES.get(x.get("category"),"其他风险"),LEVEL_NAMES.get(x.get("level"),"未评估"),x.get("trigger_reason") or "暂无说明",x.get("recommendation") or "持续跟踪"] for x in risks],widths=[3.2,1.5,5.0,5.3]);doc.add_picture(str(charts["风险等级汇总图"]),width=Cm(15));_caption(doc,"图7-1 风险等级汇总")
        for i,code in enumerate(RISK_NAMES,1):doc.add_heading(f"7.{i} {RISK_NAMES[code]}",2);item=next((x for x in risks if x.get("category")==code),None);_para(doc,(f"风险等级为{LEVEL_NAMES.get(item.get('level'),'未评估')}。{item.get('trigger_reason','')}。建议{item.get('recommendation','持续监测并滚动评估')}。" if item else "当前快照中尚未形成该项风险评估结果。"))

        doc.add_heading("8. 结论与建议",1)
        doc.add_heading("8.1 主要结论",2);_para(doc,f"{project_name}具备通过节能改造、可再生能源扩容、储能优化和绿色电力交易推进碳中和工作的基础。综合平衡场景预计减排{_num((best or {}).get('cumulative_carbon_reduction_t'))}吨二氧化碳当量，减排率为{_num(((best or {}).get('reduction_rate') or 0)*100)}%。")
        doc.add_heading("8.2 推荐路径",2);_para(doc,"建议以综合平衡场景作为近期方案深化基础，在满足能源安全和生产运行要求的前提下，优先选择技术成熟、投资回收期明确的措施。")
        doc.add_heading("8.3 实施建议",2);_para(doc,"建议建立年度碳核算和季度能源复盘机制，对光伏、风电、储能和重点用能设备开展分项计量；项目实施后应使用实际运行数据校核节能量、减排量和经济收益。")
        doc.add_heading("8.4 后续优化方向",2);_para(doc,"后续应补充现场设备参数、真实结算电价、绿电合同和运维成本，并结合连续实测数据优化模型参数，使仿真结果逐步从示范分析过渡到项目实施决策。")

        doc.add_heading("9. 附录",1);doc.add_heading("9.1 数据来源",2);_para(doc,"数据性质：示范仿真数据。报告正文使用创建时冻结快照，不读取后续变化的当前业务状态。")
        doc.add_heading("9.2 排放因子与模型版本",2);_table(doc,["项目","追溯值"],[["核算模型",account.get("model_version") or "未记录"],["排放因子来源","；".join(account.get("factor_sources") or ["快照未记录"])],["平台版本","V1.0.0-alpha.11"]],widths=[4.5,10.5])
        provenance=data.get("provenance") or {};doc.add_heading("9.3 场景、参数与任务追溯",2);_table(doc,["追溯项目","编号或说明"],[["报告编号",f"CN-RPT-{report_id:06d}"],["场景版本",str(snapshot.get("scenario_version_id"))],["仿真任务",str(snapshot.get("simulation_task_id"))],["核算记录",str(provenance.get("accounting_run_id") or "未记录")],["推荐记录",str(provenance.get("recommendation_run_id") or "未记录")],["数据时间范围",f"{task.get('start_time') or task.get('year') or '未记录'} 至 {task.get('end_time') or task.get('year') or '未记录'}"]],widths=[4.5,10.5])
        doc.add_heading("9.4 参数快照说明",2);_para(doc,"完整参数快照保存在平台不可变报告快照中。本附录仅列示主要追溯信息，避免在正文展示数据库字段、英文枚举和原始结构。")
        output_path.parent.mkdir(parents=True,exist_ok=True);doc.save(output_path)


def build_pdf(snapshot,output_path,report_id,title):
    with TemporaryDirectory() as td:
        td=Path(td);docx=td/"report.docx";build_docx(snapshot,docx,report_id,title)
        candidates=[shutil.which("soffice"),r"C:\Program Files\LibreOffice\program\soffice.exe",r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"]
        soffice=next((x for x in candidates if x and Path(x).is_file()),None)
        if not soffice:raise RuntimeError("LibreOffice is required for PDF rendering")
        profile=td/"lo-profile";profile.mkdir();cmd=[str(soffice),"--headless",f"-env:UserInstallation={profile.resolve().as_uri()}","--convert-to","pdf","--outdir",str(td),str(docx)]
        result=subprocess.run(cmd,capture_output=True,text=True,timeout=120)
        generated=td/"report.pdf"
        if result.returncode or not generated.is_file():raise RuntimeError(f"LibreOffice PDF conversion failed: {result.stderr[-500:]}")
        output_path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(generated,output_path)
