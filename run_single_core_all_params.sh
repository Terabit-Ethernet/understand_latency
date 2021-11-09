iodepth=(0 16 32 64 128)
num_apps=(1 8 16 24)
irq_cores=(1)
compute=(0 1)
for i in "${iodepth[@]}"
do
    for j in "${irq_cores[@]}"
    do
        for k in "${num_apps[@]}"
        do
            for l in "${compute[@]}"
            do
                #  ./cfs-both.sh "$num_app" temp/ 64 $i
                #  mkdir temp/cfs_single_core_"$num_app"_$i
                #  mv temp/*.log temp/cfs_single_core_"$num_app"_$i
                ./linux-both_single_core.sh $k temp/ 64 $i $l
                mkdir temp/linux_single_core_"$k"_"$i"_"$l"
                mv temp/*.log temp/linux_single_core_"$k"_"$i"_"$l"
                ./ours-both_single_core.sh $k temp/ 64 $i $j $l
                mkdir temp/our_single_core_"$k"_"$i"_"$j"_"$l"
                mv temp/*.log temp/our_single_core_"$k"_"$i"_"$j"_"$l"
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
                mkdir results/our_single_core_"$k"_"$i"_"$j"_"$l"
                ./parse-netperf.py temp/linux_single_core_"$k"_"$i"_"$k" $k > results/our_single_core_"$k"_"$i"_"$j"_"$k"/arfs_latency
                ./parse-netperf.py temp/our_single_core_"$k"_"$i"_"$j"_"$l" $k > results/our_single_core_"$k"_"$i"_"$j"_"$l"/nrfs_latency
                ./parse-breakdown-server.py temp/linux_single_core_"$k"_"$i"_"$l" $k > results/our_single_core_"$k"_"$i"_"$j"_"$l"/arfs_latency_breakdown_s
                ./parse-breakdown-server.py temp/our_single_core_"$k"_"$i"_"$j"_"$l" $k > results/our_single_core_"$k"_"$i"_"$j"_"$l"/nrfs_latency_breakdown_s
                # ./parse-breakdown.py temp/cfs_single_core_$i $i >  temp/$i/cfs_latency_breakdown_c
                ./parse-breakdown.py temp/linux_single_core_"$k"_"$i"_"$l" $k >  results/our_single_core_"$k"_"$i"_"$j"_"$l"/arfs_latency_breakdown_c
                ./parse-breakdown.py temp/our_single_core_"$k"_"$i"_"$j"_"$l" $k >  results/our_single_core_"$k"_"$i"_"$j"_"$l"/nrfs_latency_breakdown_c
                ./parse-cpu.py temp/linux_single_core_"$k"_"$i"_"$l" $k > results/our_single_core_"$k"_"$i"_"$j"_"$l"/arfs_cpu
                ./parse-cpu.py temp/our_single_core_"$k"_"$i"_"$j"_"$l" $k > results/our_single_core_"$k"_"$i"_"$j"_"$l"/nrfs_cpu
                ./parse-compute.py temp/linux_single_core_"$k"_"$i"_"$l" 2 > results/our_single_core_"$k"_"$i"_"$j"_"$l"/arfs_compute
                ./parse-compute.py temp/our_single_core_"$k"_"$i"_"$j"_"$l" 2 > results/our_single_core_"$k"_"$i"_"$j"_"$l"/nrfs_compute
            done
        done
    done
done

