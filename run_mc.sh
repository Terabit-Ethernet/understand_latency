iodepths=(0)
numflows=64
for i in "${iodepths[@]}"
do
# #  ./cfs-both-compute.sh $i temp/ 64
# #  mkdir temp/cfs_single_core_compute_$i
# #  mv temp/*.log temp/cfs_single_core_compute_$i
   ./linux-both-8c.sh $numflows temp/ 64 $i
   mkdir temp/linux_mc_"$numflows"_$i
   mv temp/*.log temp/linux_mc_"$numflows"_$i
  ./ours-both-8c.sh "$numflows" temp/ 64 $i
   mkdir temp/our_mc_"$numflows"_$i
   mv temp/*.log temp/our_mc_"$numflows"_$i 
done

#for i in "${iodepths[@]}"
#do
#	mkdir temp/$i
#	./parse-netperf.py temp/our_mc_"$numflows"_$i $numflows > temp/$i/nrfs_latency
#	./parse-netperf.py temp/linux_mc_"$numflows"_$i $numflows > temp/$i/arfs_latency
#	./parse-netperf.py temp/cfs_single_core_compute_$i $i > temp/$i/cfs_latency
#./parse-breakdown-server.py temp/cfs_single_core_$i $i > temp/$i/cfs_latency_breakdown_s
#	./parse-breakdown-server.py temp/linux_mc_"$numflows"_$i $numflows > temp/$i/arfs_latency_breakdown_s
#	./parse-breakdown-server.py temp/our_mc_"$numflows"_$i $numflows > temp/$i/nrfs_latency_breakdown_s
#./parse-breakdown.py temp/cfs_single_core_$i $i >  temp/$i/cfs_latency_breakdown_c
#	./parse-breakdown.py temp/linux_mc_"$numflows"_$i $numflows >  temp/$i/arfs_latency_breakdown_c
#	./parse-breakdown.py temp/our_mc_"$numflows"_$i $numflows >  temp/$i/nrfs_latency_breakdown_c
#	./parse-cpu.py temp/our_mc_"$numflows"_$i $numflows > temp/$i/nrfs_cpu
#./parse-cpu.py temp/cfs_single_core_$i $i > temp/$i/cfs_cpu
#	./parse-cpu.py temp/linux_mc_"$numflows"_$i $numflows > temp/$i/arfs_cpu
        # ./parse-compute.py temp/our_mc_"$numflows"_$i $numflows > temp/$i/nrfs_compute
#./parse-cpu.py temp/cfs_single_core_$i $i > temp/$i/cfs_cpu
        # ./parse-compute.py temp/linux_mc_"$numflows"_$i $numflows > temp/$i/arfs_compute
#done
