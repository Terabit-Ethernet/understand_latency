iodepth=(1)
num_apps=(256 512)
irq_cores=(2)
compute=(1)
flowsize=(redis)

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
                    ./tas-both-8c-compute-redis.sh $k temp/ $f $i $j $l
                    mkdir temp/tas_mc_"$f"_"$k"_"$i"_"$j"_"$l"
                    mv temp/*.log temp/tas_mc_"$f"_"$k"_"$i"_"$j"_"$l"
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
#                     # ./parse-cpu.py temp/linux_mc_"$f"_"$k"_"$i"_"$l" $k > results/our_mc_"$f"_"$k"_"$i"_"$j"_"$l"/arfs_cpu &
#                     # ./parse-cpu.py temp/our_mc_"$f"_"$k"_"$i"_"$j"_"$l" $k > results/our_mc_"$f"_"$k"_"$i"_"$j"_"$l"/nrfs_cpu &
#                     #  ./parse-cpu.py temp/cfs_mc_"$k"_"$i"_"$l" $k > results/our_mc_"$k"_"$i"_"$j"_"$l"/crfs_cpu &
#                     ./parse-cpu.py temp/tas_mc_"$f"_"$k"_"$i"_"$j"_"$l" $k > results/our_mc_"$f"_"$k"_"$i"_"$j"_"$l"/tas_cpu &
#                     # ./parse-compute.py temp/linux_mc_"$f"_"$k"_"$i"_"$l" 16 > results/our_mc_"$f"_"$k"_"$i"_"$j"_"$l"/arfs_compute &
#                     # ./parse-compute.py temp/our_mc_"$f"_"$k"_"$i"_"$j"_"$l" 16 > results/our_mc_"$f"_"$k"_"$i"_"$j"_"$l"/nrfs_compute &
#                     #  ./parse-compute.py temp/cfs_mc_"$k"_"$i"_"$l" 16 > results/our_mc_"$k"_"$i"_"$j"_"$l"/crfs_compute &
#                     # #  ./parse-compute.py temp/caladan_mc_"$k"_"$i"_"$j"_"$l" 8 > results/our_mc_"$k"_"$i"_"$j"_"$l"/caladan_compute &
#                     ./parse-compute.py temp/tas_mc_"$f"_"$k"_"$i"_"$j"_"$l" 16 > results/our_mc_"$f"_"$k"_"$i"_"$j"_"$l"/tas_compute &
#                     # ./parse-netperf.py temp/linux_mc_"$f"_"$k"_"$i"_"$l" $k > results/our_mc_"$f"_"$k"_"$i"_"$j"_"$l"/arfs_latency &
#                 done
#             done
#         done
#     done
# done
