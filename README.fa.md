# تحلیل قیمت و ریسک واردات قهوه

این پروژه با Python و Streamlit اجرا می‌شود. نسبت وزنی عربیکا و روبوستا، سهم ارزشی، ارزش خرید، هزینه حمل و بیمه و عوارض، حاشیه سود، سناریوهای ارز و قیمت و ریسک سه‌ماهه را محاسبه می‌کند.

## اجرای سریع در ویندوز

از پوشه پروژه:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python -m streamlit run app.py
```

رابط اصلی انگلیسی است و راهنمای فارسی در این فایل ارائه شده است.

## نکات ورود اطلاعات

- نسبت ترکیب را خودتان انتخاب کنید؛ مقدار اولیه ۶۰٪ عربیکا صرفاً مثال است.
- واحد ورودی و نمایش را ریال یا تومان انتخاب کنید؛ تبدیل داخلی خودکار است. در حالت تومان، عدد را خودتان در ۱۰ ضرب نکنید.
- داده قهوه از FRED/IMF، میانگین ماهانه است و قیمت لحظه‌ای یا پیشنهاد فروش تأمین‌کننده نیست.
- نرخ خودکار دلار یک نرخ مرجع است؛ نرخ بازار آزاد یا ارز قابل تسویه شما تأیید نشده است.
- دریافت داده، ورودی دستی را خودکار جایگزین نمی‌کند؛ منبع فعال را انتخاب کنید.
- برای قیمت قطعی خرید، درصد قیمت تثبیت‌نشده قهوه را صفر کنید. این کار ریسک ارز را حذف نمی‌کند.
- تاریخچه نمونه کاملاً مصنوعی است؛ هیچ عدد نمونه‌ای به عنوان داده زنده معرفی نمی‌شود.
- این برنامه مدل آماری و شبیه‌سازی دارد؛ ادعای هوش مصنوعی آموزش‌دیده ندارد.

## خروجی‌ها و محدودیت‌ها

VaR و CVaR در این برنامه ریسک افزایش هزینه نسبت به هزینه مبنا هستند. احتمال زیان یعنی احتمال منفی شدن سود با قیمت فروش ثابت. حاشیه سود بر درآمد تقسیم می‌شود، نه هزینه.

شش نقطه ماهانه برای برآورد قابل اتکای ریسک کافی نیست. کالیبراسیون حداقل ۱۳ ماه و پس‌آزمایی حداقل ۲۷ ماه تاریخچه هم‌زمان نیاز دارد؛ تاریخچه طولانی‌تر مناسب‌تر است. پس‌آزمایی با داده‌های تاریخی بازبینی‌شده انجام می‌شود و ارزیابی معامله واقعی در زمان انتشار نیست.

راهنمای کامل فرمول‌ها، منابع، آزمون‌ها و انتشار در گیت‌هاب در README.md آمده است. فایل JSON خروجی، ورودی‌ها و منابع و seed را ذخیره می‌کند و با replay.py قابل بازتولید است.


## Operational release — 2026-10-27

See [the detailed evaluation](reports/2026-10-27-release/RELEASE_REVIEW_FA.md) and [numeric results](reports/2026-10-27-release/results.json). IRR/toman conversion, component costs, roasting/sales allocations, five operational engines, evidence manifests, private documents and digest-checked future forecast records are implemented. Private records are excluded from Git and Docker build contexts. No uploaded invoice has been independently verified.

The dated example [manifest](reports/2026-10-27-release/market-scenario-manifest.json) uses actual monthly FRED benchmarks and user-reported 271,000 toman/USD with explicitly assumed commercial costs. Load via Shipment evidence. It is not an actual trade invoice or a live retail quote. Snapshot values remain dated; fetching new data does not imply transaction verification.

The history-only FX identity is not an exchange rate feed. Set FX unfixed=0 for operational coffee-only scenarios; retrospective tests are USD-only. Manual GBM risk assumptions remain separate from history-based forecasts. zero_log makes simulated terminal mean log growth equal across methods; it does not equalize expected arithmetic growth. No model is automatically promoted.

68 tests passed, and all five engines were exercised through Streamlit AppTest with real fetched history; audit replay matched exactly. Raw market history stays outside the repository. Results still show inadequate risk coverage and large mismatches to some seller listings. No forced fit to market prices or guarantee of decision accuracy is claimed. See the report for all assumptions and failed comparisons. Run `python evaluate_release.py` to reproduce this dated release scenario; retailer/FX reference observations in that script are frozen on 2026-10-27, not automatically refreshed quotes. The forecast registry is local and digest-checked, not trusted timestamping. Do not represent past-data tests as prospective validation.

## انتشار ۱ نوامبر ۲۰۲۶

کد و شواهد نسخه عملیاتی منتشر شده‌اند. [گزارش انتشار و بازآزمایی](reports/PUBLICATION_2026-11-01.md). قیمت‌ها و اجرای واقعی گزارش‌های مهر/اکتبر، تاریخ اصلی خود را حفظ می‌کنند و قیمت لحظه‌ای روز انتشار نیستند.
