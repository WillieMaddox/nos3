/************************************************************************
 * NOS3-specific CS Application Table.
 * Checksums the loaded application code segments so a corrupted/replaced app
 * (EX-0009 code exploitation, EX-0012.03 memory write) produces a miscompare.
 * cFE core (CFE_ES/EVS/SB/TBL/TIME) is covered separately by CS_CFECORE_CHECKSUM.
 * The idle lab stubs (CI_LAB_APP/TO_LAB_APP) and the SAMPLE demo are omitted.
 ************************************************************************/
#include "cfe.h"
#include "cfe_tbl_filedef.h"
#include "cs_msgdefs.h"
#include "cs_platform_cfg.h"
#include "cs_tbldefs.h"

CS_Def_App_Table_Entry_t CS_AppTable[CS_MAX_NUM_APP_TABLE_ENTRIES] = {
    /*  0 */ {.State = CS_STATE_ENABLED, .Name = "SCH"},
    /*  1 */ {.State = CS_STATE_ENABLED, .Name = "CI"},
    /*  2 */ {.State = CS_STATE_ENABLED, .Name = "TO"},
    /*  3 */ {.State = CS_STATE_ENABLED, .Name = "CS"},
    /*  4 */ {.State = CS_STATE_ENABLED, .Name = "CF"},
    /*  5 */ {.State = CS_STATE_ENABLED, .Name = "DS"},
    /*  6 */ {.State = CS_STATE_ENABLED, .Name = "FM"},
    /*  7 */ {.State = CS_STATE_ENABLED, .Name = "LC"},
    /*  8 */ {.State = CS_STATE_ENABLED, .Name = "SBN"},
    /*  9 */ {.State = CS_STATE_ENABLED, .Name = "SC"},
    /* 10 */ {.State = CS_STATE_ENABLED, .Name = "ADCS"},
    /* 11 */ {.State = CS_STATE_ENABLED, .Name = "CSS"},
    /* 12 */ {.State = CS_STATE_ENABLED, .Name = "EPS"},
    /* 13 */ {.State = CS_STATE_ENABLED, .Name = "FSS"},
    /* 14 */ {.State = CS_STATE_ENABLED, .Name = "NAV"},
    /* 15 */ {.State = CS_STATE_ENABLED, .Name = "IMU"},
    /* 16 */ {.State = CS_STATE_ENABLED, .Name = "MGR"},
    /* 17 */ {.State = CS_STATE_ENABLED, .Name = "MAG"},
    /* 18 */ {.State = CS_STATE_ENABLED, .Name = "RADIO"},
    /* 19 */ {.State = CS_STATE_ENABLED, .Name = "RW"},
    /* 20 */ {.State = CS_STATE_ENABLED, .Name = "ST"},
    /* 21 */ {.State = CS_STATE_ENABLED, .Name = "THRUSTER"},
    /* 22 */ {.State = CS_STATE_ENABLED, .Name = "TORQUER"},
    /* 23 */ {.State = CS_STATE_EMPTY,   .Name = ""}};

CFE_TBL_FILEDEF(CS_AppTable, CS.DefAppTbl, CS App Tbl, cs_apptbl.tbl)
