set title "DGPS 3D Test Results"
set xlabel "Sample 1Hz"
set ylabel "Error (m)"
set style data lines
set terminal png
set output "DGPS-err.png"
plot "errlog.txt" using "normal" title "GPS-3D", '' using "DGPS" title "DGPS-3D"

