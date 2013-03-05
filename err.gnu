set title "DGPS Test Results"
set xlabel "Sample 1Hz"
set ylabel "Error (m)"
set style data lines
plot "errlog.txt" using "normal", '' using "DGPS", '' using "normal-XY", '' using "DGPS-XY"
