//+------------------------------------------------------------------+
//| NUNG_Bridge.mq5 — THIN BODY only (Phase 3B-B)                      |
//| No strategy, no ML, no risk intelligence, no autonomous decisions. |
//| Responsibilities: IPC HELLO, heartbeat, state report, order relay. |
//+------------------------------------------------------------------+
#property copyright "N.U.N.G"
#property version   "0.1.0"
#property description "Thin NUNG bridge EA — infrastructure only"

// Contract source for installer. Do NOT add indicators or entry logic.

input string InpHost = "127.0.0.1";
input int    InpPort = 0;

int OnInit()
{
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason) {}
void OnTick() {}
void OnTimer() {}
//+------------------------------------------------------------------+
