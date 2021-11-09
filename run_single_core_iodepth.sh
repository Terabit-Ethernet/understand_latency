iodepth=(128)
num_app=8
irq_cores=(1 2 3 4)
for i in "${iodepth[@]}"
do
    for j in "${irq_cores[@]}"
    do
    #  ./cfs-both.sh "$num_app" temp/ 64 $i
    #  mkdir temp/cfs_single_core_"$num_app"_$i
    #  mv temp/*.log temp/cfs_single_core_"$num_app"_$i
    # ./linux-both.sh $num_app temp/ 64 $i $j
    # mkdir temp/linux_single_core_"$num_app"_"$i"_"$j"
    # mv temp/*.log temp/linux_single_core_"$num_app"_"$i"_"$j"
    ./ours-both.sh "$num_app" temp/ 64 $i $j
    mkdir temp/our_single_core_"$num_app"_"$i"_"$j"
    mv temp/*.log temp/our_single_core_"$num_app"_"$i"_"$j"
    done
done

for i in "${iodepth[@]}"
do
    mkdir temp/$i
    for j in "${irq_cores[@]}"
    do
    mkdir temp/$i/$j
    # ./parse-netperf.py temp/linux_single_core_"$num_app"_"$i"_"$j" $num_app > temp/$i/$j/arfs_latency
    ./parse-netperf.py temp/our_single_core_"$num_app"_"$i"_"$j" $num_app > temp/$i/$j/nrfs_latency
    # ./parse-netperf.py temp/cfs_single_core_$i $i > temp/$i/cfs_latency
    # ./parse-breakdown-server.py temp/cfs_single_core_$i $i > temp/$i/cfs_latency_breakdown_s
    # ./parse-breakdown-server.py temp/linux_single_core_"$num_app"_"$i"_"$j" $num_app > temp/$i/$j/arfs_latency_breakdown_s
    ./parse-breakdown-server.py temp/our_single_core_"$num_app"_"$i"_"$j" $num_app > temp/$i/$j/nrfs_latency_breakdown_s
    # ./parse-breakdown.py temp/cfs_single_core_$i $i >  temp/$i/cfs_latency_breakdown_c
    # ./parse-breakdown.py temp/linux_single_core_"$num_app"_"$i"_"$j" $num_app >  temp/$i/$j/arfs_latency_breakdown_c
    ./parse-breakdown.py temp/our_single_core_"$num_app"_"$i"_"$j" $num_app >  temp/$i/$j/nrfs_latency_breakdown_c
    # ./parse-cpu.py temp/linux_single_core_"$num_app"_"$i"_"$j" $num_app > temp/$i/$j/arfs_cpu
    ./parse-cpu.py temp/our_single_core_"$num_app"_"$i"_"$j" $num_app > temp/$i/$j/nrfs_cpu
    # ./parse-cpu.py temp/cfs_single_core_$i $i > temp/$i/cfs_cpu
    done
done

