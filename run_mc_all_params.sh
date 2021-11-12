iodepth=(0)
num_apps=(128)
irq_cores=(2)
compute=(1)
for i in "${iodepth[@]}"
do
    for j in "${irq_cores[@]}"
    do
        for k in "${num_apps[@]}"
        do
            for l in "${compute[@]}"
            do
                ./cfs-both-compute.sh "$k" temp/ 64 $i
                mkdir temp/cfs_mc_"$k"_"$i"_"$l"
                mv temp/*.log temp/cfs_mc_"$k"_"$i"_"$l"
                ./linux-both-8c-compute.sh $k temp/ 64 $i $l
                mkdir temp/linux_mc_"$k"_"$i"_"$l"
                mv temp/*.log temp/linux_mc_"$k"_"$i"_"$l"
                ./ours-both-8c-compute-k2.sh $k temp/ 64 $i $j $l
                mkdir temp/our_mc_"$k"_"$i"_"$j"_"$l"
                mv temp/*.log temp/our_mc_"$k"_"$i"_"$j"_"$l"
            done
        done
    done
done

mkdir results
for i in "${iodepth[@]}"
do
    for j in "${irq_cores[@]}"
    do
        for k in "${num_apps[@]}"
        do
            for l in "${compute[@]}"
            do
                mkdir results/our_mc_"$k"_"$i"_"$j"_"$l"
                ./parse-netperf.py temp/linux_mc_"$k"_"$i"_"$l" $k > results/our_mc_"$k"_"$i"_"$j"_"$l"/arfs_latency &
                ./parse-netperf.py temp/our_mc_"$k"_"$i"_"$j"_"$l" $k > results/our_mc_"$k"_"$i"_"$j"_"$l"/nrfs_latency &
                ./parse-netperf.py temp/cfs_mc_"$k"_"$i"_"$l" $k > results/our_mc_"$k"_"$i"_"$j"_"$l"/crfs_latency &
                ./parse-breakdown-server.py temp/linux_mc_"$k"_"$i"_"$l" $k > results/our_mc_"$k"_"$i"_"$j"_"$l"/arfs_latency_breakdown_s &
                ./parse-breakdown-server.py temp/our_mc_"$k"_"$i"_"$j"_"$l" $k > results/our_mc_"$k"_"$i"_"$j"_"$l"/nrfs_latency_breakdown_s &
                ./parse-breakdown-server.py temp/cfs_mc_"$k"_"$i"_"$l" $k > results/our_mc_"$k"_"$i"_"$j"_"$l"/crfs_latency_breakdown_s &
                # ./parse-breakdown.py temp/cfs_mc_$i $i >  temp/$i/cfs_latency_breakdown_c
                ./parse-breakdown.py temp/linux_mc_"$k"_"$i"_"$l" $k >  results/our_mc_"$k"_"$i"_"$j"_"$l"/arfs_latency_breakdown_c &
                ./parse-breakdown.py temp/our_mc_"$k"_"$i"_"$j"_"$l" $k >  results/our_mc_"$k"_"$i"_"$j"_"$l"/nrfs_latency_breakdown_c &
                ./parse-breakdown.py temp/cfs_mc_"$k"_"$i"_"$l" $k >  results/our_mc_"$k"_"$i"_"$j"_"$l"/crfs_latency_breakdown_c &
                ./parse-cpu.py temp/linux_mc_"$k"_"$i"_"$l" $k > results/our_mc_"$k"_"$i"_"$j"_"$l"/arfs_cpu &
                ./parse-cpu.py temp/our_mc_"$k"_"$i"_"$j"_"$l" $k > results/our_mc_"$k"_"$i"_"$j"_"$l"/nrfs_cpu &
                ./parse-cpu.py temp/cfs_mc_"$k"_"$i"_"$l" $k > results/our_mc_"$k"_"$i"_"$j"_"$l"/crfs_cpu &
                ./parse-compute.py temp/linux_mc_"$k"_"$i"_"$l" 8 > results/our_mc_"$k"_"$i"_"$j"_"$l"/arfs_compute &
                ./parse-compute.py temp/our_mc_"$k"_"$i"_"$j"_"$l" 8 > results/our_mc_"$k"_"$i"_"$j"_"$l"/nrfs_compute &
                ./parse-compute.py temp/cfs_mc_"$k"_"$i"_"$l" 8 > results/our_mc_"$k"_"$i"_"$j"_"$l"/crfs_compute &

            done
        done
    done
done
