iodepth=(1 2 4 8)
num_apps=(128)
irq_cores=(4)
compute=(1)
flowsize=(64)

# for f in "${flowsize[@]}"
# do  
#     for i in "${iodepth[@]}"
#     do
#             for k in "${num_apps[@]}"
#             do
#                 for l in "${compute[@]}"
#                 do
#                     ./linux-both-8c-compute-hd.sh $k temp/ $f $i $l
#                     mkdir temp/linux_mc_"$f"_"$k"_"$i"_"$l"
#                     mv temp/*.log temp/linux_mc_"$f"_"$k"_"$i"_"$l"
#                 done
#             done
#     done
# done

# for f in "${flowsize[@]}"
# do  
#     for i in "${iodepth[@]}"
#     do
#         for j in "${irq_cores[@]}"
#         do
#             for k in "${num_apps[@]}"
#             do
#                 for l in "${compute[@]}"
#                 do
#                     ./ours-both-8c-compute-k2-hd.sh $k temp/ $f $i $j $l
#                     mkdir temp/our_mc_"$f"_"$k"_"$i"_"$j"_"$l"
#                     mv temp/*.log temp/our_mc_"$f"_"$k"_"$i"_"$j"_"$l"
#                 done
#             done
#         done
#     done
# done

for f in "${flowsize[@]}"
do  
    for i in "${iodepth[@]}"
    do
        for k in "${num_apps[@]}"
        do
            for l in "${compute[@]}"
            do
                ./tas-both-8c-compute.sh $k temp/ $f $i
                mkdir temp/tas_mc_"$f"_"$k"_"$i"_"$l"
                mv temp/*.log temp/tas_mc_"$f"_"$k"_"$i"_"$l"
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
#                     mkdir results/our_mc_"$f"_"$k"_"$i"_"$j"_"$l"
#                     ./parse-netperf.py temp/linux_mc_"$f"_"$k"_"$i"_"$l" $k > results/our_mc_"$f"_"$k"_"$i"_"$j"_"$l"/arfs_latency &
#                     ./parse-breakdown-server.py temp/linux_mc_"$f"_"$k"_"$i"_"$l" $k > results/our_mc_"$f"_"$k"_"$i"_"$j"_"$l"/arfs_latency_breakdown_s &
#                     ./parse-breakdown.py temp/linux_mc_"$f"_"$k"_"$i"_"$l" $k >  results/our_mc_"$f"_"$k"_"$i"_"$j"_"$l"/arfs_latency_breakdown_c &
#                     ./parse-cpu.py temp/linux_mc_"$f"_"$k"_"$i"_"$l" $k > results/our_mc_"$f"_"$k"_"$i"_"$j"_"$l"/arfs_cpu &
#                     ./parse-compute.py temp/linux_mc_"$f"_"$k"_"$i"_"$l" 16 > results/our_mc_"$f"_"$k"_"$i"_"$j"_"$l"/arfs_compute &
#                 done
#             done
#         done
#     done
# done

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
#                     ./parse-netperf.py temp/our_mc_"$f"_"$k"_"$i"_"$j"_"$l" $k > results/our_mc_"$f"_"$k"_"$i"_"$j"_"$l"/nrfs_latency &
#                     ./parse-breakdown-server.py temp/our_mc_"$f"_"$k"_"$i"_"$j"_"$l" $k > results/our_mc_"$f"_"$k"_"$i"_"$j"_"$l"/nrfs_latency_breakdown_s &
#                     ./parse-breakdown.py temp/our_mc_"$f"_"$k"_"$i"_"$j"_"$l" $k >  results/our_mc_"$f"_"$k"_"$i"_"$j"_"$l"/nrfs_latency_breakdown_c &
#                     ./parse-cpu.py temp/our_mc_"$f"_"$k"_"$i"_"$j"_"$l" $k > results/our_mc_"$f"_"$k"_"$i"_"$j"_"$l"/nrfs_cpu &
#                     ./parse-compute.py temp/our_mc_"$f"_"$k"_"$i"_"$j"_"$l" 16 > results/our_mc_"$f"_"$k"_"$i"_"$j"_"$l"/nrfs_compute &
#                 done
#             done
#         done
#     done
# done

for f in  "${flowsize[@]}"
do
    for i in "${iodepth[@]}"
    do
        for j in "${irq_cores[@]}"
        do
            for k in "${num_apps[@]}"
            do
                for l in "${compute[@]}"
                do
                    mkdir results/our_mc_"$f"_"$k"_"$i"_"$j"_"$l"
                    ./parse-netperf-tas.py temp/tas_mc_"$f"_"$k"_"$i"_"$l" $k > results/our_mc_"$f"_"$k"_"$i"_"$j"_"$l"/tas_latency &
                    ./parse-cpu.py temp/tas_mc_"$f"_"$k"_"$i"_"$l" $k > results/our_mc_"$f"_"$k"_"$i"_"$j"_"$l"/tas_cpu &
                    ./parse-compute.py temp/tas_mc_"$f"_"$k"_"$i"_"$l" 16 > results/our_mc_"$f"_"$k"_"$i"_"$j"_"$l"/tas_compute &
                done
            done
        done
    done
done
