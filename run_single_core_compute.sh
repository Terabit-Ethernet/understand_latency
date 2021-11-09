flows=(1 2 4 8)
for i in "${flows[@]}"
do
  ./cfs-both-compute.sh $i temp/ 64
  mkdir temp/cfs_single_core_compute_$i
  mv temp/*.log temp/cfs_single_core_compute_$i
  ./linux-both-compute.sh $i temp/ 64
  mkdir temp/linux_single_core_compute_$i
  mv temp/*.log temp/linux_single_core_compute_$i
 ./ours-both-compute.sh $i temp/ 64
  mkdir temp/our_single_core_compute_$i
  mv temp/*.log temp/our_single_core_compute_$i 
done

#for i in "${flows[@]}"
#do
#mkdir temp/$i
#./parse-netperf.py temp/our_single_core_compute_$i $i > temp/$i/nrfs_latency
#./parse-netperf.py temp/linux_single_core_compute_$i $i > temp/$i/arfs_latency
#./parse-netperf.py temp/cfs_single_core_compute_$i $i > temp/$i/cfs_latency
#./parse-breakdown-server.py temp/cfs_single_core_$i $i > temp/$i/cfs_latency_breakdown_s
#./parse-breakdown-server.py temp/linux_single_core_$i $i > temp/$i/arfs_latency_breakdown_s
#./parse-breakdown-server.py temp/our_single_core_$i $i > temp/$i/nrfs_latency_breakdown_s
#./parse-breakdown.py temp/cfs_single_core_$i $i >  temp/$i/cfs_latency_breakdown_c
#./parse-breakdown.py temp/linux_single_core_$i $i >  temp/$i/arfs_latency_breakdown_c
#./parse-breakdown.py temp/our_single_core_$i $i >  temp/$i/nrfs_latency_breakdown_c
#./parse-cpu.py temp/our_single_core_$i $i > temp/$i/nrfs_cpu
#./parse-cpu.py temp/cfs_single_core_$i $i > temp/$i/cfs_cpu
#./parse-cpu.py temp/linux_single_core_$i $i > temp/$i/arfs_cpu
#done
