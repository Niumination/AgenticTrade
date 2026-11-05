//+------------------------------------------------------------------+
//|                                               AgenticTrade.mq5   |
//|  Prototipe EA — enforcement hard-coded dari docs/RISK.md         |
//|  Strategi: docs/STRATEGY.md v0.1 (Sniper Desk + Sweep Hunter)    |
//|                                                                  |
//|  Pagar risiko ini NON-NEGOTIABLE: nilai guard hard-coded konstan,|
//|  tidak diekspos sebagai input yang bisa diubah user.             |
//|  Cakupan: prototipe SATU simbol — EA hanya mengeksekusi sinyal   |
//|  pada simbol chart (_Symbol) yang juga ada di ALLOWED_SYMBOLS.   |
//+------------------------------------------------------------------+
#property copyright "AgenticTrade"
#property version   "0.1.0"
#property strict

#include <Trade/Trade.mqh>

//--- Enum status guard
enum GUARD_STATE
  {
   GUARD_OK = 0,        // trading diizinkan
   GUARD_DAILY_LOSS,    // loss harian >= 3% -> stop sampai hari berikutnya
   GUARD_KILL_SWITCH,   // DD ekuitas dari HWM >= 10% -> stop total
   GUARD_MAX_POSITIONS, // sudah 2 posisi paralel
   GUARD_NO_SL,         // sinyal tanpa SL ditolak
   GUARD_NEWS_WINDOW,   // di dalam jendela news merah +/- 15 menit
   GUARD_RISK_TOO_WIDE, // jarak SL membuat lot < lot minimum broker
   GUARD_OUTSIDE_KILLZONE, // setup 2 hanya di Killzone (London/NY)
   GUARD_INVALID_SIGNAL,   // sinyal tanpa reasoning valid ditolak
   GUARD_SYMBOL_NOT_ALLOWED, // simbol di luar daftar instrumen resmi
   GUARD_SYMBOL_MISMATCH     // simbol sinyal != simbol chart EA (prototipe 1-simbol)
  };

//+------------------------------------------------------------------+
//| Pagar risiko hard-coded (docs/RISK.md) — JANGAN diubah ke input  |
//+------------------------------------------------------------------+
const double RISK_PCT_PER_TRADE   = 1.0;   // maks 1% ekuitas per posisi
const double DAILY_LOSS_PCT_LIMIT = 3.0;   // 3% loss harian -> stop hari itu
const double EQUITY_DD_PCT_LIMIT  = 10.0;  // 10% DD dari HWM -> kill switch
const int    MAX_OPEN_POSITIONS   = 2;     // maks 2 posisi paralel
const int    NEWS_BLOCK_MINUTES   = 15;    // dilarang trading +/- 15 menit news
const double MIN_RR_SNIPER        = 1.8;   // RR minimum setup 1 (STRATEGY.md)
const double MIN_RR_SWEEP         = 2.0;   // RR minimum setup 2 (STRATEGY.md)

//--- Daftar instrumen resmi (RISK.md: dilarang eksekusi di luar daftar ini)
//--- TODO koordinator: konfirmasi daftar final sebelum rilis.
const string ALLOWED_SYMBOLS[] = { "XAUUSD", "EURUSD", "GBPUSD" };

//--- Magic number EA (identitas order milik EA ini)
const long EA_MAGIC = 20261104;

//--- Killzone (jam server, UTC): London 07-10, NY 12-15
const int KZ_LONDON_START = 7,  KZ_LONDON_END = 10;
const int KZ_NY_START     = 12, KZ_NY_END     = 15;

//+------------------------------------------------------------------+
//| State global                                                     |
//+------------------------------------------------------------------+
CTrade         trade;
double         g_equity_hwm      = 0.0;   // high-water mark ekuitas
datetime       g_current_day     = 0;     // penanda hari (server time)
bool           g_daily_stopped   = false; // daily-loss guard aktif?
bool           g_kill_switch     = false; // kill switch aktif? (butuh review manual)

//--- Struktur sinyal yang dikirim relay (dari modul analysis/ via file/queue)
struct Signal
  {
   string   id;            // id unik sinyal (untuk log & dedup)
   int      setup;         // 1 = Sniper Desk, 2 = Sweep Hunter
   string   symbol;
   int      direction;     // ORDER_TYPE_BUY / ORDER_TYPE_SELL
   double   entry;
   double   sl;            // WAJIB > 0
   double   tp;
   string   reasoning;     // WAJIB non-kosong (STRATEGY.md: tanpa reasoning = bug)
   datetime news_event_time; // waktu rilis high-impact terdekat; 0 jika tidak ada
  };

//+------------------------------------------------------------------+
//| Initialization                                                   |
//+------------------------------------------------------------------+
int OnInit()
  {
   trade.SetExpertMagicNumber(EA_MAGIC);
   trade.SetDeviationInPoints(20);
   trade.SetTypeFillingBySymbol(_Symbol);
   g_equity_hwm = AccountInfoDouble(ACCOUNT_EQUITY);
   PrintFormat("AgenticTrade v0.1.0 init | HWM=%.2f | guards: 1%%/trade, 3%% daily, 10%% DD kill, max %d pos, news +/-%d min",
               g_equity_hwm, MAX_OPEN_POSITIONS, NEWS_BLOCK_MINUTES);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
//| Main tick: update HWM, cek kill switch, kelola guard harian      |
//+------------------------------------------------------------------+
void OnTick()
  {
   UpdateDailyRollover();
   UpdateEquityHwm();
   if(CheckKillSwitch())
     {
      CloseAllPositions("kill switch 10% DD");
      return;
     }
   // Prototipe: pemrosesan sinyal dipanggil dari relay; OnTick hanya menjaga guard.
   // EvaluateSignal dipanggil oleh ProcessSignal() (dipicu relay/polling).
  }

//+------------------------------------------------------------------+
//| Rollover harian: reset guard loss harian di awal hari baru       |
//+------------------------------------------------------------------+
void UpdateDailyRollover()
  {
   datetime today = iTime(_Symbol, PERIOD_D1, 0);
   if(today != g_current_day)
     {
      g_current_day   = today;
      g_daily_stopped = false; // pagi baru: daily-loss guard di-reset
      PrintFormat("Rollover harian %s — daily-loss guard reset", TimeToString(today, TIME_DATE));
     }
  }

//+------------------------------------------------------------------+
//| Update high-water mark ekuitas                                   |
//+------------------------------------------------------------------+
void UpdateEquityHwm()
  {
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   if(eq > g_equity_hwm)
      g_equity_hwm = eq;
  }

//+------------------------------------------------------------------+
//| Kill switch: DD ekuitas dari HWM >= 10% -> stop total permanen   |
//| (butuh review manual; hanya reset manual oleh operator)          |
//+------------------------------------------------------------------+
bool CheckKillSwitch()
  {
   if(g_kill_switch)
      return(true);
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   if(g_equity_hwm <= 0.0)
      return(false);
   double dd_pct = (g_equity_hwm - eq) / g_equity_hwm * 100.0;
   if(dd_pct >= EQUITY_DD_PCT_LIMIT)
     {
      g_kill_switch = true;
      LogGuard(GUARD_KILL_SWITCH,
               StringFormat("DD ekuitas %.2f%% >= %.2f%% dari HWM %.2f — SISTEM STOP TOTAL, review manual wajib",
                            dd_pct, EQUITY_DD_PCT_LIMIT, g_equity_hwm));
      return(true);
     }
   return(false);
  }

//+------------------------------------------------------------------+
//| Daily-loss guard: loss harian >= 3% -> stop sampai hari berikut  |
//+------------------------------------------------------------------+
bool CheckDailyLoss()
  {
   if(g_kill_switch)
      return(true);
   if(g_daily_stopped)
      return(true);
   // Kalkulasi P/L closed hari ini (deals history, hari berjalan)
   double closed_pl = 0.0;
   datetime day_start = g_current_day;
   if(HistorySelect(day_start, TimeCurrent()))
     {
      int total = HistoryDealsTotal();
      for(int i = 0; i < total; i++)
        {
         ulong ticket = HistoryDealGetTicket(i);
         if(ticket == 0)
            continue;
         if(HistoryDealGetInteger(ticket, DEAL_ENTRY) == DEAL_ENTRY_OUT ||
            HistoryDealGetInteger(ticket, DEAL_ENTRY) == DEAL_ENTRY_INOUT)
            closed_pl += HistoryDealGetDouble(ticket, DEAL_PROFIT)
                       + HistoryDealGetDouble(ticket, DEAL_SWAP)
                       + HistoryDealGetDouble(ticket, DEAL_COMMISSION);
        }
     }
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double day_start_equity = balance - closed_pl; // aproksimasi ekuitas awal hari
   if(day_start_equity <= 0.0)
      return(false);
   double loss_pct = -closed_pl / day_start_equity * 100.0;
   if(loss_pct >= DAILY_LOSS_PCT_LIMIT)
     {
      g_daily_stopped = true;
      LogGuard(GUARD_DAILY_LOSS,
               StringFormat("Loss harian %.2f%% >= %.2f%% — trading berhenti sampai hari berikutnya",
                            loss_pct, DAILY_LOSS_PCT_LIMIT));
      return(true);
     }
   return(false);
  }

//+------------------------------------------------------------------+
//| News filter: tolak entry +/- 15 menit sekitar news high-impact   |
//+------------------------------------------------------------------+
bool InNewsWindow(const Signal &sig)
  {
   if(sig.news_event_time == 0)
      return(false);
   datetime now = TimeCurrent();
   datetime window_start = sig.news_event_time - NEWS_BLOCK_MINUTES * 60;
   datetime window_end   = sig.news_event_time + NEWS_BLOCK_MINUTES * 60;
   if(now >= window_start && now <= window_end)
     {
      LogGuard(GUARD_NEWS_WINDOW,
               StringFormat("Sinyal %s di dalam jendela news +/-%d menit (%s) — ditolak",
                            sig.id, NEWS_BLOCK_MINUTES, TimeToString(sig.news_event_time)));
      return(true);
     }
   return(false);
  }

//+------------------------------------------------------------------+
//| Killzone check untuk setup 2 (Sweep Hunter) — server time UTC    |
//+------------------------------------------------------------------+
bool InKillzone()
  {
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   int h = dt.hour;
   bool london = (h >= KZ_LONDON_START && h < KZ_LONDON_END);
   bool ny     = (h >= KZ_NY_START     && h < KZ_NY_END);
   return(london || ny);
  }

//+------------------------------------------------------------------+
//| Hitung jumlah posisi terbuka milik EA ini                        |
//+------------------------------------------------------------------+
int CountOwnPositions()
  {
   int count = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol &&
         PositionGetInteger(POSITION_MAGIC) == EA_MAGIC)
         count++;
     }
   return(count);
  }

//+------------------------------------------------------------------+
//| Ukuran lot dari risiko 1% ekuitas dan jarak SL                   |
//+------------------------------------------------------------------+
double CalcLotByRisk(double entry, double sl)
  {
   double equity    = AccountInfoDouble(ACCOUNT_EQUITY);
   double risk_money = equity * RISK_PCT_PER_TRADE / 100.0;
   double tick_size  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tick_value = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   if(tick_size <= 0.0 || tick_value <= 0.0)
      return(0.0);
   double sl_distance = MathAbs(entry - sl);
   if(sl_distance <= 0.0)
      return(0.0);
   double loss_per_lot = sl_distance / tick_size * tick_value;
   if(loss_per_lot <= 0.0)
      return(0.0);
   double lots = risk_money / loss_per_lot;
   // Normalisasi ke step/lot min/max broker
   double lot_step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double lot_min  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double lot_max  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   if(lot_step > 0.0)
      lots = MathFloor(lots / lot_step) * lot_step;
   if(lots < lot_min)
      return(0.0); // jarak SL terlalu lebar utk 1% risiko -> guard RISK_TOO_WIDE
   if(lots > lot_max)
      lots = lot_max;
   return(lots);
  }

//+------------------------------------------------------------------+
//| Simbol di dalam daftar instrumen resmi? (docs/RISK.md)           |
//+------------------------------------------------------------------+
bool SymbolAllowed(const string symbol)
  {
   for(int i = 0; i < ArraySize(ALLOWED_SYMBOLS); i++)
      if(ALLOWED_SYMBOLS[i] == symbol)
         return(true);
   return(false);
  }

//+------------------------------------------------------------------+
//| Core: evaluasi sinyal terhadap SEMUA guard sebelum eksekusi      |
//| Return: true jika order terkirim. Semua penolakan terlog.        |
//+------------------------------------------------------------------+
bool ProcessSignal(const Signal &sig)
  {
   // G0: kill switch & daily loss
   if(CheckKillSwitch())
      return(false);
   if(CheckDailyLoss())
      return(false);

   // G1: simbol harus di daftar instrumen resmi (docs/RISK.md)
   if(!SymbolAllowed(sig.symbol))
     {
      LogGuard(GUARD_SYMBOL_NOT_ALLOWED,
               StringFormat("Sinyal %s pada simbol '%s' di luar daftar instrumen resmi — DITOLAK", sig.id, sig.symbol));
      return(false);
     }

   // G1b: prototipe berjalan satu simbol per chart — tolak simbol lain agar
   // kalkulasi risiko (CalcLotByRisk) dan guard posisi/kill-switch selalu
   // konsisten dengan simbol eksekusi.
   if(sig.symbol != _Symbol)
     {
      LogGuard(GUARD_SYMBOL_MISMATCH,
               StringFormat("Sinyal %s simbol '%s' != simbol chart '%s' (prototipe 1-simbol) — DITOLAK", sig.id, sig.symbol, _Symbol));
      return(false);
     }

   // G2: sinyal wajib punya reasoning valid (STRATEGY.md — tanpa reasoning = BUG)
   if(StringLen(sig.reasoning) == 0)
     {
      LogGuard(GUARD_INVALID_SIGNAL, StringFormat("Sinyal %s tanpa reasoning — DITOLAK (bug, bukan fitur)", sig.id));
      return(false);
     }

   // G2: SL wajib ada
   if(sig.sl <= 0.0)
     {
      LogGuard(GUARD_NO_SL, StringFormat("Sinyal %s tanpa SL — DITOLAK", sig.id));
      return(false);
     }

   // G3: maks 2 posisi paralel
   if(CountOwnPositions() >= MAX_OPEN_POSITIONS)
     {
      LogGuard(GUARD_MAX_POSITIONS,
               StringFormat("Sinyal %s ditolak: sudah %d posisi paralel (maks %d)",
                            sig.id, CountOwnPositions(), MAX_OPEN_POSITIONS));
      return(false);
     }

   // G4: news filter
   if(InNewsWindow(sig))
      return(false);

   // G5: killzone hanya untuk setup 2; RR minimum per setup
   double min_rr = (sig.setup == 2) ? MIN_RR_SWEEP : MIN_RR_SNIPER;
   if(sig.setup == 2 && !InKillzone())
     {
      LogGuard(GUARD_OUTSIDE_KILLZONE, StringFormat("Sinyal %s (setup 2) di luar Killzone — ditolak", sig.id));
      return(false);
     }
   double rr = 0.0;
   double risk_dist = MathAbs(sig.entry - sig.sl);
   double reward_dist = MathAbs(sig.tp - sig.entry);
   if(risk_dist > 0.0)
      rr = reward_dist / risk_dist;
   if(rr < min_rr)
     {
      LogGuard(GUARD_INVALID_SIGNAL,
               StringFormat("Sinyal %s RR %.2f < minimum %.2f (setup %d) — ditolak", sig.id, rr, min_rr, sig.setup));
      return(false);
     }

   // G6: ukuran lot dari risiko 1%
   double lots = CalcLotByRisk(sig.entry, sig.sl);
   if(lots <= 0.0)
     {
      LogGuard(GUARD_RISK_TOO_WIDE,
               StringFormat("Sinyal %s: jarak SL menghasilkan lot < lot minimum pada risiko 1%% — ditolak", sig.id));
      return(false);
     }

   // Eksekusi dengan SL/TP terpasang (wajib)
   bool sent = false;
   if(sig.direction == ORDER_TYPE_BUY)
      sent = trade.Buy(lots, sig.symbol, 0.0, sig.sl, sig.tp, sig.id);
   else if(sig.direction == ORDER_TYPE_SELL)
      sent = trade.Sell(lots, sig.symbol, 0.0, sig.sl, sig.tp, sig.id);
   else
     {
      LogGuard(GUARD_INVALID_SIGNAL, StringFormat("Sinyal %s arah tidak dikenal (%d) — ditolak", sig.id, sig.direction));
      return(false);
     }

   if(sent)
      PrintFormat("ORDER OK: %s %s %.2f lot @ market, SL=%.5f TP=%.5f RR=%.2f | reasoning: %s",
                  sig.symbol, (sig.direction == ORDER_TYPE_BUY ? "BUY" : "SELL"),
                  lots, sig.sl, sig.tp, rr, sig.reasoning);
   else
      PrintFormat("ORDER FAILED: %s retcode=%d (%s)", sig.id, trade.ResultRetcode(), trade.ResultRetcodeDescription());
   return(sent);
  }

//+------------------------------------------------------------------+
//| Tutup semua posisi EA (dipakai kill switch)                      |
//+------------------------------------------------------------------+
void CloseAllPositions(const string reason)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol &&
         PositionGetInteger(POSITION_MAGIC) == EA_MAGIC)
        {
         trade.PositionClose(ticket);
         PrintFormat("CLOSE #%I64u — %s", ticket, reason);
        }
     }
  }

//+------------------------------------------------------------------+
//| Log guard: setiap pelanggaran wajib terlog (bukti EA bekerja)    |
//+------------------------------------------------------------------+
void LogGuard(const GUARD_STATE state, const string detail)
  {
   PrintFormat("[GUARD %d] %s", (int)state, detail);
   // TODO fase berikut: append ke signals log (append-only, divalidasi CI)
  }
//+------------------------------------------------------------------+
