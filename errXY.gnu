set title "DGPS 2D Test Results"
set xlabel "Sample 1Hz"
set ylabel "Error (m)"
set style data lines
set terminal png
set output "DGPS-errXY.png"
plot "errlog.txt" using "normal-XY" title "GPS-2D", '' using "DGPS-XY" title "DGPS-2D"
