iodepth=(1)
num_apps=(1024 2048)
irq_cores=(2)
compute=(1)
flowsize=(64)

for f in "${flowsize[@]}"
do  
    for i in "${iodepth[@]}"
    do
        for j in "${irq_cores[@]}"
        do
            for k in "${num_apps[@]}"
            do
                for l in "${compute[@]}"
                do
                    ./linux-both-8c-compute-redis.sh $k temp/ $f $i $l
                    mkdir temp/linux_sc_"$f"_"$k"_"$i"_"$l"
                    mv temp/*.log temp/linux_sc_"$f"_"$k"_"$i"_"$l"
                    ./ours-both-8c-compute-k2-redis.sh $k temp/ $f $i $j $l
                    mkdir temp/our_mc_"$f"_"$k"_"$i"_"$j"_"$l"
                    mv temp/*.log temp/our_mc_"$f"_"$k"_"$i"_"$j"_"$l"
                done
            done
        done
    done
done

# mkdir results
# for f in  "${flowsize[@]}"
# do
#     for i in "${iodepth[@]}"
#     do
#         for j in "${irq_cores[@]}"
#         do
#             for k in "${num_apps[@]}"
#             do
#                 for l in "${compute[@]}"
#                 do
#                     mkdir results/our_sc_"$f"_"$k"_"$i"_"$j"_"$l"
#                     #  ./parse-neper.py temp/linux_mc_"$f"_"$k"_"$i"_"$l" $k > results/our_mc_"$f"_"$k"_"$i"_"$j"_"$l"/arfs_latency &
#                     # ./parse-neper.py temp/our_mc_"$f"_"$k"_"$i"_"$j"_"$l" $k > results/our_mc_"$f"_"$k"_"$i"_"$j"_"$l"/nrfs_latency &
#                     # ./parse-neper.py temp/cfs_mc_"$f"_"$k"_"$i"_"$l" $k > results/our_sc_"$f"_"$k"_"$i"_"$j"_"$l"/crfs_latency &
#                     # ./parse-neper.py temp/caladan_mc_"$k"_"$i"_"$j"_"$l" $k > results/our_mc_"$k"_"$i"_"$j"_"$l"/caladan_latency &
#                     # ./parse-neper.py temp/tas_mc_"$f"_"$k"_"$i"_"$j"_"$l" $k > results/our_mc_"$f"_"$k"_"$i"_"$j"_"$l"/tas_latency &
#                     ./parse-netperf.py temp/linux_sc_"$f"_"$k"_"$i"_"$l" $k > results/our_sc_"$f"_"$k"_"$i"_"$j"_"$l"/arfs_latency &
#                     # ./parse-netperf.py temp/our_sc_"$f"_"$k"_"$i"_"$j"_"$l" $k > results/our_sc_"$f"_"$k"_"$i"_"$j"_"$l"/nrfs_latency &
#                     #  ./parse-netperf.py temp/cfs_sc_"$f"_"$k"_"$i"_"$l" $k > results/our_sc_"$f"_"$k"_"$i"_"$j"_"$l"/crfs_latency &
#                     #  ./parse-netperf.py temp/caladan_mc_"$k"_"$i"_"$j"_"$l" $k > results/our_mc_"$k"_"$i"_"$j"_"$l"/caladan_latency &
#                     #  ./parse-netperf-tas.py temp/tas_mc_"$f"_"$k"_"$i"_"$j"_"$l" $k > results/our_mc_"$f"_"$k"_"$i"_"$j"_"$l"/tas_latency &
#                     ./parse-breakdown-server.py temp/linux_sc_"$f"_"$k"_"$i"_"$l" $k > results/our_sc_"$f"_"$k"_"$i"_"$j"_"$l"/arfs_latency_breakdown_s &
#                     # ./parse-breakdown-server.py temp/our_mc_"$f"_"$k"_"$i"_"$j"_"$l" $k > results/our_mc_"$f"_"$k"_"$i"_"$j"_"$l"/nrfs_latency_breakdown_s &
#                     #  ./parse-breakdown-server.py temp/cfs_mc_"$f"_"$k"_"$i"_"$l" $k > results/our_mc_"$f"_"$k"_"$i"_"$j"_"$l"/crfs_latency_breakdown_s &
#                     ./parse-breakdown.py temp/linux_sc_"$f"_"$k"_"$i"_"$l" $k >  results/our_sc_"$f"_"$k"_"$i"_"$j"_"$l"/arfs_latency_breakdown_c &
#                     # ./parse-breakdown.py temp/our_sc_"$f"_"$k"_"$i"_"$j"_"$l" $k >  results/our_sc_"$f"_"$k"_"$i"_"$j"_"$l"/nrfs_latency_breakdown_c &
#                     #  ./parse-breakdown.py temp/cfs_mc_"$f"_"$k"_"$i"_"$l" $k >  results/our_mc_"$f"_"$k"_"$i"_"$j"_"$l"/crfs_latency_breakdown_c &
#                     # ./parse-cpu.py temp/linux_mc_"$f"_"$k"_"$i"_"$l" $k > results/our_mc_"$f"_"$k"_"$i"_"$j"_"$l"/arfs_cpu &
#                     # ./parse-cpu.py temp/our_mc_"$f"_"$k"_"$i"_"$j"_"$l" $k > results/our_mc_"$f"_"$k"_"$i"_"$j"_"$l"/nrfs_cpu &
#                     #  ./parse-cpu.py temp/cfs_mc_"$k"_"$i"_"$l" $k > results/our_mc_"$k"_"$i"_"$j"_"$l"/crfs_cpu &
#                     # ./parse-cpu.py temp/tas_mc_"$f"_"$k"_"$i"_"$j"_"$l" $k > results/our_mc_"$f"_"$k"_"$i"_"$j"_"$l"/tas_cpu &
#                     # ./parse-compute.py temp/linux_mc_"$f"_"$k"_"$i"_"$l" 16 > results/our_mc_"$f"_"$k"_"$i"_"$j"_"$l"/arfs_compute &
#                     # ./parse-compute.py temp/our_mc_"$f"_"$k"_"$i"_"$j"_"$l" 16 > results/our_mc_"$f"_"$k"_"$i"_"$j"_"$l"/nrfs_compute &
#                     #  ./parse-compute.py temp/cfs_mc_"$k"_"$i"_"$l" 16 > results/our_mc_"$k"_"$i"_"$j"_"$l"/crfs_compute &
#                     # #  ./parse-compute.py temp/caladan_mc_"$k"_"$i"_"$j"_"$l" 8 > results/our_mc_"$k"_"$i"_"$j"_"$l"/caladan_compute &
#                     #  ./parse-compute.py temp/tas_mc_"$f"_"$k"_"$i"_"$j"_"$l" 16 > results/our_mc_"$f"_"$k"_"$i"_"$j"_"$l"/tas_compute &

#                 done
#             done
#         done
#     done
# done
