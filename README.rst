ping-multi-ext
**************

This tool lets you interactively ping:

* One host from multiple locations (via SSH)
* Multiple hosts from one location (local machine, or remote via SSH)
* Multiple hosts from multiple locations (via SSH)

The ping results are summarized in real-time and you can
also observe the following statistics:

* TX_cnt: Count of sent PING requests
* RX_cnt: Count of received PING replies which are not timeouts
* XX_cnt: Count of timeouts and missing PING replies
* Loss%: Packet loss defined as the percentage of timed out and missing replies
* Avg: Average round trip time (RTT)
* Min: Minimum (best) RTT
* Max: Maximum (worst) RTT
* StDev: Population standard deviation of all RTT data

The interactive UI interface lets you visualize the RTT summary in three modes:

* Successful vs. unsuccessful PING replies
* The RTT values (ping time) as a number
* Scaled per 100 ms where "0" means an RTT between 0 and 99 ms,
  "1" means an RTT between 100 and 199 ms, and so on

You also have the option to review each host's "ping" command raw output.
The full history is kept and you can navigate using the keys PgUp/PgDn/Home/End.
