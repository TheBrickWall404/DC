"""
Scoring calculator implementing the Chen Auto CV Algorithm.
"""
from typing import List, Dict
from config import SPEAKING_POINTS_TABLE
from database import get_connection
from name_matcher import get_name_variations

class ChenCVCalculator:
    @staticmethod
    def map_team_rank_to_stage(rank: int, format_type: str = "BP") -> str:
        if format_type in ["Australs", "AP", "World Schools", "WS"]:
            if rank == 1: return "Win"
            if rank == 2: return "GF"
            if rank <= 4: return "SF"
            if rank <= 8: return "QF"
            if rank <= 16: return "OF"
            if rank <= 32: return "DOF"
            return "QOF"
        
        # Standard BP
        if rank == 1: return "Win"
        if rank <= 4: return "GF"
        if rank <= 8: return "SF"
        if rank <= 16: return "QF"
        if rank <= 32: return "OF"
        if rank <= 64: return "DOF"
        return "QOF"

    @staticmethod
    def map_speaker_rank_to_stage(rank: int, format_type: str = "BP") -> str:
        if format_type in ["Australs", "AP", "World Schools", "WS"]:
            if rank <= 3: return "Win"
            if rank <= 6: return "GF"
            if rank <= 12: return "SF"
            if rank <= 24: return "QF"
            if rank <= 48: return "OF"
            if rank <= 96: return "DOF"
            return "QOF"

        # Standard BP
        if rank <= 2: return "Win"
        if rank <= 8: return "GF"
        if rank <= 16: return "SF"
        if rank <= 32: return "QF"
        if rank <= 64: return "OF"
        if rank <= 128: return "DOF"
        return "QOF"

    @classmethod
    def calculate_speaking_cv(cls, participant_names: List[str]) -> Dict:
        norm_keys = set()
        for n in participant_names:
            norm_keys.update(get_name_variations(n))

        conn = get_connection()
        cur = conn.cursor()

        placeholders = ",".join("?" * len(norm_keys))
        cur.execute(f"SELECT id, raw_name FROM participants WHERE normalized_name IN ({placeholders})", list(norm_keys))
        p_rows = cur.fetchall()

        if not p_rows:
            conn.close()
            return {"error": f"No records found for aliases: {participant_names}"}

        p_ids = [r[0] for r in p_rows]
        p_placeholders = ",".join("?" * len(p_ids))

        query = f"""
        SELECT DISTINCT t.id, t.slug, t.name, t.speaking_class, t.format, t.is_prm
        FROM tournaments t
        JOIN team_members tm ON t.id = tm.tournament_id
        WHERE tm.participant_id IN ({p_placeholders})
        """
        cur.execute(query, p_ids)
        tournaments = cur.fetchall()

        raw_achievements = []
        breakdown = []

        for t_id, slug, t_name, s_class, fmt, is_prm in tournaments:
            prm_bonus = 0.4 if is_prm else 0.0

            cur.execute(f"""
                SELECT tm.team_name, tm.avg_speaks
                FROM team_members tm
                WHERE tm.tournament_id = ? AND tm.participant_id IN ({p_placeholders})
            """, [t_id] + p_ids)
            member_record = cur.fetchone()

            team_adj, spk_adj = 0.0, 0.0
            team_name = None
            if member_record:
                team_name, my_speaks = member_record
                cur.execute(f"""
                    SELECT avg_speaks FROM team_members
                    WHERE tournament_id = ? AND team_name = ? AND participant_id NOT IN ({p_placeholders})
                """, [t_id, team_name] + p_ids)
                partner = cur.fetchone()

                if partner and partner[0] and my_speaks:
                    diff = my_speaks - partner[0]
                    if diff <= -1.01:            team_adj, spk_adj = -1.6, -0.8
                    elif -1.00 <= diff <= -0.75: team_adj, spk_adj = -0.8, -0.4
                    elif diff >= 1.01:           team_adj, spk_adj = +0.4, 0.0
                    elif 0.75 <= diff <= 1.00:   team_adj, spk_adj = +0.2, 0.0

            # 1. Furthest Open Outround
            outround_desc = "None"
            if team_name:
                cur.execute("SELECT stage FROM outrounds WHERE tournament_id = ? AND team_name = ? AND is_open = 1", (t_id, team_name))
                out_row = cur.fetchone()
                if out_row:
                    stage = out_row[0]
                    base_pts = SPEAKING_POINTS_TABLE.get(s_class, {}).get(stage, 0.0)
                    pts = max(0.0, base_pts + prm_bonus + team_adj)
                    outround_desc = f"{stage} ({pts:.2f} pts)"
                    raw_achievements.append(pts)

            # 2. Team Tab (Top 50% check)
            team_tab_desc = "None"
            if team_name:
                cur.execute("SELECT team_rank, total_teams, is_eligible FROM team_tab WHERE tournament_id = ? AND team_name = ?", (t_id, team_name))
                tt_row = cur.fetchone()
                if tt_row and tt_row[2] == 1:
                    stage = cls.map_team_rank_to_stage(tt_row[0], fmt)
                    base_pts = SPEAKING_POINTS_TABLE.get(s_class, {}).get(stage, 0.0)
                    pts = max(0.0, base_pts + prm_bonus + team_adj)
                    team_tab_desc = f"Rank {tt_row[0]}/{tt_row[1]} -> {stage} ({pts:.2f} pts)"
                    raw_achievements.append(pts)

            # 3. Speaker Tab (Top 50% check)
            spk_tab_desc = "None"
            cur.execute(f"SELECT speaker_rank, total_speakers, is_eligible FROM speaker_tab WHERE tournament_id = ? AND participant_id IN ({p_placeholders})", [t_id] + p_ids)
            st_row = cur.fetchone()
            if st_row and st_row[2] == 1:
                stage = cls.map_speaker_rank_to_stage(st_row[0], fmt)
                base_pts = SPEAKING_POINTS_TABLE.get(s_class, {}).get(stage, 0.0)
                pts = max(0.0, base_pts + prm_bonus + spk_adj)
                spk_tab_desc = f"Rank {st_row[0]}/{st_row[1]} -> {stage} ({pts:.2f} pts)"
                raw_achievements.append(pts)

            breakdown.append({
                "tournament": t_name,
                "class": s_class,
                "is_prm": bool(is_prm),
                "open_outround": outround_desc,
                "team_tab": team_tab_desc,
                "speaker_tab": spk_tab_desc
            })

        # Savings Provisions: Ghost Copies (-0.8 pts step)
        pool = list(raw_achievements)
        for pts in raw_achievements:
            ghost = pts - 0.8
            while ghost > 0.0:
                pool.append(round(ghost, 2))
                ghost -= 0.8

        pool.sort(reverse=True)
        top_10 = pool[:10]
        cv_score = round(sum(top_10) / len(top_10), 2) if top_10 else 0.0

        conn.close()

        return {
            "matched_names": list({r[1] for r in p_rows}),
            "tournaments": breakdown,
            "top_10_achievements": top_10,
            "speaking_cv_score": cv_score
        }