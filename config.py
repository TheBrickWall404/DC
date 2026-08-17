"""
Configuration parameters and points tables based on the Chen Auto Debating CV Algorithm.
"""

DB_FILE = "debate_cv.db"

# Eligible tournament classes (S-C and above)
ELIGIBLE_CLASSES = {
    "S-WUDC", "S-AAA+", "S-AAA", "S-AA+", "S-AA", "S-A+", "S-A", "S-B", "S-C"
}

# Premier Regional Majors getting +0.4 bonus
PRM_KEYWORDS = ["wudc", "eudc", "australs", "uadc", "naudc", "abp", "paudc", "cmude", "wsdc"]

# Standard Speaking Points Table
SPEAKING_POINTS_TABLE = {
    "S-WUDC": {"Win": 10.2, "GF": 9.4, "SF": 8.6, "QF": 7.8, "OF": 7.0, "DOF": 6.2, "QOF": 5.4},
    "S-AAA+": {"Win": 9.8,  "GF": 9.0, "SF": 8.2, "QF": 7.4, "OF": 6.6, "DOF": 5.8, "QOF": 5.0},
    "S-AAA":  {"Win": 9.4,  "GF": 8.6, "SF": 7.8, "QF": 7.0, "OF": 6.2, "DOF": 5.4, "QOF": 4.6},
    "S-AA+":  {"Win": 9.0,  "GF": 8.2, "SF": 7.4, "QF": 6.6, "OF": 5.8, "DOF": 5.0, "QOF": 4.2},
    "S-AA":   {"Win": 8.6,  "GF": 7.8, "SF": 7.0, "QF": 6.2, "OF": 5.4, "DOF": 4.6, "QOF": 3.8},
    "S-A+":   {"Win": 8.2,  "GF": 7.4, "SF": 6.6, "QF": 5.8, "OF": 5.0, "DOF": 4.2, "QOF": 3.4},
    "S-A":    {"Win": 7.8,  "GF": 7.0, "SF": 6.2, "QF": 5.4, "OF": 4.6, "DOF": 3.8, "QOF": 3.0},
    "S-B":    {"Win": 7.0,  "GF": 6.2, "SF": 5.4, "QF": 4.6, "OF": 3.8, "DOF": 3.0, "QOF": 2.2},
    "S-C":    {"Win": 6.2,  "GF": 5.4, "SF": 4.6, "QF": 3.8, "OF": 3.0, "DOF": 2.2, "QOF": 1.4},
}

# Outround stage hierarchy
STAGE_HIERARCHY = {
    "Win": 7,
    "GF": 6,
    "SF": 5,
    "QF": 4,
    "OF": 3,
    "DOF": 2,
    "QOF": 1
}