"""模块2：库存决策沙盘API"""

import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from database import get_connection
from models.simulation import SandboxInput, SandboxResult
from services.sandbox_simulator import run_simulation
from services.pdf_generator import generate_report_html

router = APIRouter(prefix="/api/sandbox", tags=["库存决策沙盘"])


@router.post("/simulate", response_model=SandboxResult)
async def simulate(inp: SandboxInput):
    """运行五路径模拟"""
    result = run_simulation(inp)

    # 保存到数据库
    conn = get_connection()
    cursor = conn.execute(
        """INSERT INTO sandbox_results
           (car_description, entry_date, overdue_amount, che300_value, daily_parking,
            input_json, path_a_json, path_b_json, path_c_json, path_d_json, path_e_json,
            recommendation, best_path)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            inp.car_description, inp.entry_date, inp.overdue_amount,
            inp.che300_value, inp.daily_parking,
            inp.model_dump_json(),
            result.path_a.model_dump_json(),
            result.path_b.model_dump_json(),
            result.path_c.model_dump_json(),
            result.path_d.model_dump_json(),
            result.path_e.model_dump_json(),
            result.recommendation,
            result.best_path,
        ),
    )
    result.id = cursor.lastrowid
    conn.commit()
    conn.close()

    return result


@router.get("/{result_id}")
async def get_result(result_id: int):
    """获取模拟结果"""
    conn = get_connection()
    row = conn.execute("SELECT * FROM sandbox_results WHERE id = ?", (result_id,)).fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="模拟结果不存在")

    return {
        "id": row["id"],
        "car_description": row["car_description"],
        "entry_date": row["entry_date"],
        "overdue_amount": row["overdue_amount"],
        "che300_value": row["che300_value"],
        "input": json.loads(row["input_json"]) if row["input_json"] else None,
        "path_a": json.loads(row["path_a_json"]),
        "path_b": json.loads(row["path_b_json"]),
        "path_c": json.loads(row["path_c_json"]),
        "path_d": json.loads(row["path_d_json"]) if row["path_d_json"] else None,
        "path_e": json.loads(row["path_e_json"]) if row["path_e_json"] else None,
        "recommendation": row["recommendation"],
        "best_path": row["best_path"],
        "created_at": row["created_at"],
    }


@router.post("/{result_id}/report", response_class=HTMLResponse)
async def generate_report(result_id: int):
    """生成PDF报告（返回HTML预览）"""
    conn = get_connection()
    row = conn.execute("SELECT * FROM sandbox_results WHERE id = ?", (result_id,)).fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="模拟结果不存在")

    # 从保存的完整数据重建SandboxResult
    inp_data = row["input_json"]
    if inp_data:
        inp = SandboxInput.model_validate_json(inp_data)
    else:
        inp = SandboxInput(
            car_description=row["car_description"],
            entry_date=row["entry_date"],
            overdue_amount=row["overdue_amount"],
            che300_value=row["che300_value"],
            daily_parking=row["daily_parking"],
        )

    from models.simulation import PathAResult, PathBResult, PathCResult, PathDResult, PathEResult
    result = SandboxResult(
        id=row["id"],
        input=inp,
        path_a=PathAResult.model_validate_json(row["path_a_json"]),
        path_b=PathBResult.model_validate_json(row["path_b_json"]),
        path_c=PathCResult.model_validate_json(row["path_c_json"]),
        path_d=PathDResult.model_validate_json(row["path_d_json"]) if row["path_d_json"] else run_simulation(inp).path_d,
        path_e=PathEResult.model_validate_json(row["path_e_json"]) if row["path_e_json"] else run_simulation(inp).path_e,
        recommendation=row["recommendation"],
        best_path=row["best_path"] or "C",
    )

    html = await generate_report_html(result)
    return HTMLResponse(content=html)


@router.get("/list/all")
async def list_results():
    """列出所有模拟结果"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, car_description, che300_value, recommendation, created_at FROM sandbox_results ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
