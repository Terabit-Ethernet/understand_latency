# iodepth=(1)
# num_apps=(128)
# irq_cores=(4)
# compute=(1)
# flowsize=(64)

iodepth=(1)
num_apps=(16 32 64 128 256 512 1024 2048)
flowsize=(64)
dim=(1)
pin=(1)
tapp=(0)
sched=(1)
irq_cores=(3 4 5 6)
threads=(16)
hrtimer=0
for d in "${dim[@]}"
do  
    for p in "${pin[@]}"
    do
        for t in "${tapp[@]}"
        do
            for s in "${sched[@]}"
            do
                # for f in "${flowsize[@]}"
                # do  
                #     for i in "${iodepth[@]}"
                #     do
                #         for irq in "${irq_cores[@]}"
                #         do
                #             for th in "${threads[@]}"
                #             do
                #                 for k in "${num_apps[@]}"
                #                 do
                #                     ./ours-both-8c-compute-k2-neper.sh $k temp/ $f $i $irq $d $p $t $s $th $hrtimer
                #                     mkdir temp/our_epoll_"$f"_"$k"_"$i"_"$th"_"$irq"_"$hrtimer"
                #                     mv temp/*.log temp/our_epoll_"$f"_"$k"_"$i"_"$th"_"$irq"_"$hrtimer"
                #                     echo "done"    
                #                 done
                #             done
                #         done
                #     done
                # done
                # mkdir temp/dim_"$d"_pin_"$p"_tapp_"$t"_sched_"$s"
                # cp -r temp/our_epoll* temp/dim_"$d"_pin_"$p"_tapp_"$t"_sched_"$s" && rm -rf temp/our_epoll*
                for f in  "${flowsize[@]}"
                do
                    for i in "${iodepth[@]}"
                    do
                        for irq in "${irq_cores[@]}"
                        do
                            for th in "${threads[@]}"
                            do
                                for k in "${num_apps[@]}"
                                do
                                    mkdir results/our_epoll_"$f"_"$k"_"$i"_"$th"_"$irq"_"$hrtimer"
                                    ./parse-neper.py temp/dim_"$d"_pin_"$p"_tapp_"$t"_sched_"$s"/our_epoll_"$f"_"$k"_"$i"_"$th"_"$irq"_"$hrtimer" $k > results/our_epoll_"$f"_"$k"_"$i"_"$th"_"$irq"_"$hrtimer"/nrfs_latency &
                                    ./parse-breakdown-server.py temp/dim_"$d"_pin_"$p"_tapp_"$t"_sched_"$s"/our_epoll_"$f"_"$k"_"$i"_"$th"_"$irq"_"$hrtimer" $k > results/our_epoll_"$f"_"$k"_"$i"_"$th"_"$irq"_"$hrtimer"/nrfs_latency_breakdown_s &
                                    ./parse-breakdown.py temp/dim_"$d"_pin_"$p"_tapp_"$t"_sched_"$s"/our_epoll_"$f"_"$k"_"$i"_"$th"_"$irq"_"$hrtimer" $k >  results/our_epoll_"$f"_"$k"_"$i"_"$th"_"$irq"_"$hrtimer"/nrfs_latency_breakdown_c &
                                    # ./parse-cpu.py temp/our_epoll_"$f"_"$k"_"$i" $k $j > results/our_epoll_"$f"_"$k"_"$i"/arfs_cpu &
                                    ./parse-compute.py temp/dim_"$d"_pin_"$p"_tapp_"$t"_sched_"$s"/our_epoll_"$f"_"$k"_"$i"_"$th"_"$irq"_"$hrtimer" 16 > results/our_epoll_"$f"_"$k"_"$i"_"$th"_"$irq"_"$hrtimer"/nrfs_compute &
                                done
                            done
                        done
                    done
                done
                wait $PIDS
                mkdir results/dim_"$d"_pin_"$p"_tapp_"$t"_sched_"$s"
                cp -r results/our_epoll* results/dim_"$d"_pin_"$p"_tapp_"$t"_sched_"$s"  && rm -rf results/our_epoll*
                PIDS=""
            done
        done
    done
done


# for f in "${flowsize[@]}"
# do  
#     for i in "${iodepth[@]}"
#     do
#             for k in "${num_apps[@]}"
#             do
#                 for l in "${compute[@]}"
#                 do
#                     ./linux-both-8c-compute-neper.sh $k temp/ $f $i $l
#                     mkdir temp/linux_epoll_"$f"_"$k"_"$i"_"$l"
#                     mv temp/*.log temp/linux_epoll_"$f"_"$k"_"$i"_"$l"
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
#                     ./ours-both-8c-compute-k2-neper.sh $k temp/ $f $i $j $l
#                     mkdir temp/our_epoll_"$f"_"$k"_"$i"_"$j"_"$l"
#                     mv temp/*.log temp/our_epoll_"$f"_"$k"_"$i"_"$j"_"$l"
#                 done
#             done
#         done
#     done
# done

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
#                     mkdir results/our_epoll_"$f"_"$k"_"$i"_"$j"_"$l"
#                     ./parse-neper.py temp/linux_epoll_"$f"_"$k"_"$i"_"$l" $k > results/our_epoll_"$f"_"$k"_"$i"_"$j"_"$l"/arfs_latency &
#                     ./parse-breakdown-server.py temp/linux_epoll_"$f"_"$k"_"$i"_"$l" $k > results/our_epoll_"$f"_"$k"_"$i"_"$j"_"$l"/arfs_latency_breakdown_s &
#                     ./parse-breakdown.py temp/linux_epoll_"$f"_"$k"_"$i"_"$l" $k >  results/our_epoll_"$f"_"$k"_"$i"_"$j"_"$l"/arfs_latency_breakdown_c &
#                     ./parse-cpu.py temp/linux_epoll_"$f"_"$k"_"$i"_"$l" $k > results/our_epoll_"$f"_"$k"_"$i"_"$j"_"$l"/arfs_cpu &
#                     ./parse-compute.py temp/linux_epoll_"$f"_"$k"_"$i"_"$l" 16 > results/our_epoll_"$f"_"$k"_"$i"_"$j"_"$l"/arfs_compute &
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
#                     mkdir results/our_epoll_"$f"_"$k"_"$i"_"$j"_"$l"
#                     ./parse-neper.py temp/our_epoll_"$f"_"$k"_"$i"_"$j"_"$l" $k > results/our_epoll_"$f"_"$k"_"$i"_"$j"_"$l"/nrfs_latency &
#                     ./parse-breakdown-server.py temp/our_epoll_"$f"_"$k"_"$i"_"$j"_"$l" $k > results/our_epoll_"$f"_"$k"_"$i"_"$j"_"$l"/nrfs_latency_breakdown_s &
#                     ./parse-breakdown.py temp/our_epoll_"$f"_"$k"_"$i"_"$j"_"$l" $k >  results/our_epoll_"$f"_"$k"_"$i"_"$j"_"$l"/nrfs_latency_breakdown_c &
#                     ./parse-cpu.py temp/our_epoll_"$f"_"$k"_"$i"_"$j"_"$l" $k > results/our_epoll_"$f"_"$k"_"$i"_"$j"_"$l"/nrfs_cpu &
#                     ./parse-compute.py temp/our_epoll_"$f"_"$k"_"$i"_"$j"_"$l" 16 > results/our_epoll_"$f"_"$k"_"$i"_"$j"_"$l"/nrfs_compute &
#                 done
#             done
#         done
#     done
# done
