Every minute do the following:
1. Ping Translink API for stops: 50987 (15), 50996 (15), 60349 (R4), 60535 (9 and 99)
2. Report the next two times for each specified route on the stop.
3. For R4, add a 10 minute delay. For example, if current time is 10:03 AM, the earlist time that can be displayed is 10:13 AM.
4. For 9 and 99, add a 20 minute delay. Also filter out trips that do not go to "Boundary Loop"
5. Display these results as follows:
---------------------------------------------
| 15 [Olympic]           3, 19 min| <-- right align
| 15 [Place]         now, 16 min|
| R4 [Place]     12, 14 min|
| 9 [Place]          4, 11 min|
| 99 [Place]          4, 11 min|
---------------------------------------------
6. Use the font "luminator Horizon" and size the text appriopriately to take the full display