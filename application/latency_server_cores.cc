/* Copyright (c) 2019, Stanford University
 *
 * Permission to use, copy, modify, and/or distribute this software for any
 * purpose with or without fee is hereby granted, provided that the above
 * copyright notice and this permission notice appear in all copies.
 *
 * THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
 * WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
 * MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
 * ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
 * WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
 * ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
 * OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
 */

/* This is a test program that acts as a server for testing either
 * Homa or TCP; it simply accepts request packets of arbitrary length
 * and responds with packets whose length is determined by the request.
 * The program runs forever; use control-C to kill it.
 *
 * Usage:
 * server [options]
 * 
 * Type "server --help" for documenation on the options.
 */
#include <arpa/inet.h>
#include <atomic>
#include <chrono>         // std::chrono::seconds

#include <iostream>
#include <fstream>
#include <mutex>
#include <condition_variable>
#include <list>
#include <errno.h>
#include <netdb.h>
#include <netinet/in.h>
#include <netinet/tcp.h>

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include <netinet/ip.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/syscall.h>
#include <inttypes.h>
#include <thread>
#include <vector>
// #include "homa.h"
#include "test_utils.h"
#include <sys/resource.h>
#include <sstream>


#define SERVER_PRINT_VRUNTIME

//#include "../uapi_linux_nd.h"
/* Log events to standard output. */
bool verbose = false;

/* Port number on which to listen (both for Homa and TCP); if multiple
 * Homa ports are in use, they will be consecutive numbers starting with
 * this. */
int port = 4000;

/* True that a specific format is expected for incoming messages, and we
 * should check that incoming messages conform to it.
 */
bool validate = false;

int thread_count = 1;
std::atomic<int> connected_count;

class Conn_Data {
public:
	int fd;
	struct sockaddr_in source;
	int iodepth;
	int flow_size;
	Conn_Data(int fd, struct sockaddr_in source, int iodepth, int flow_size) {
		this->fd = fd;
		this->source = source;
		this->iodepth = iodepth;
		this->flow_size = flow_size;	
	}
	Conn_Data(){}
};
struct Agg_Stats {
	std::atomic<unsigned long> total_bytes;
	std::atomic<unsigned long> interval_bytes;
	uint64_t start_cycle;
	int interval_sec;
};

struct Agg_Stats agg_stats;
void init_agg_stats(struct Agg_Stats* stats, int interval_sec) {
	atomic_store(&stats->total_bytes, (unsigned long)0);
	atomic_store(&stats->interval_bytes, (unsigned long)0);
	stats->start_cycle = rdtsc();
	stats->interval_sec = interval_sec;
}

std::mutex mtx;           // mutex for critical section
std::condition_variable cv;
std::list<Conn_Data> socklist;

void aggre_thread(struct Agg_Stats *stats) {
	init_agg_stats(stats, 1);
	while(1) {
		uint64_t start_cycle = rdtsc();
		uint64_t end_cycle;
		double rate;
		double bytes;
    	std::this_thread::sleep_for (std::chrono::seconds(stats->interval_sec));
    	end_cycle = rdtsc();
    	bytes = atomic_load(&stats->interval_bytes);
    	rate = (bytes)/ to_seconds(
			end_cycle - start_cycle);
		printf("Throughput: "
		"%.2f Gbps, bytes: %f, time: %f\n", rate * 1e-09 * 8, (double) bytes, to_seconds(
		end_cycle - start_cycle));
    	atomic_store(&stats->interval_bytes, (unsigned long)0);
	}
}

double diff_timespec(const struct timespec *time1, const struct timespec *time0) {
  return (time1->tv_sec - time0->tv_sec)
      + (time1->tv_nsec - time0->tv_nsec) / 1000000000.0;
}

/**
 * nd_pingpong() - Handles messages arriving on a given socket.
 * @fd:           File descriptor for the socket over which messages
 *                will arrive.
 * @client_addr:  Information about the client (for messages).
 */
void nd_pingpong(int fd, struct sockaddr_in source, int iodepth, int flow_size)
{
	// std::unique_lock<std::mutex> lck(mtx);
	// atomic_fetch_add(&connected_count, 1);
	// if(atomic_load(&connected_count) == thread_count) {
	// 	lck.unlock();
	// 	cv.notify_all();
	// }
	// else {
	// 	cv.wait(lck, []{ return atomic_load(&connected_count) == thread_count; });
	// 	lck.unlock();
	// }
	// int flag = 1;
	bool is_first = false;
	struct timespec first_time;
	// Conn_Data data;
	int optval = 6;
	unsigned optlen = 0;
	char buffer[9000];
	int flag;
	// int iodepth;
	unsigned int cpu, node;


	// int times = 10000;
	// int cur_length = 0;
	// bool streaming = false;
	uint64_t count = 0;
	uint64_t total_length = 0;
	// uint64_t start_cycle = 0, end_cycle = 0;
	struct sockaddr_in sin;
	socklen_t len = sizeof(sin);
	// int which = PRIO_PROCESS;
	pid_t pid = syscall(__NR_gettid);
//	struct sched_param param;
//	param.sched_priority = 99;
//    	sched_setscheduler(pid, SCHED_RR, &param);
	//ret = setpriority(which, pid, -20);
	//std::cout << "ret "<< ret << std::endl;
	// ret = getpriority(which, pid);
	// int *int_buffer = reinterpret_cast<int*>(buffer);
	if (verbose)
		printf("New ND socket from %s\n", print_address(&source));
	// setsockopt(fd, IPPROTO_TCP, TCP_NODELAY, &flag, sizeof(flag));
	if (getpeername(fd, (struct sockaddr *)&sin, &len) == -1)
	    perror("getsockname");
	flag = 1;
//	setsockopt(fd, IPPROTO_TCP, TCP_NODELAY, &flag, sizeof(int));
	flag = 0;
//	printf("core: %d pid: %d port number: %d\n",cpu,  pid, ntohs(sin.sin_port));
//	fflush (stdout);
	// start_cycle = rdtsc();
	setsockopt(fd, SOL_SOCKET, SO_PRIORITY, &optval, unsigned(sizeof(optval)));   
	getsockopt(fd, SOL_SOCKET, SO_PRIORITY, &optval, &optlen);

	// printf("sizeof buffer:%ld\n", sizeof(buffer));
	while (1) {
		int copied = 0;
		int rpc_length = flow_size;
		// times--;
		// int burst = iodepth;
		while(1) {
			int result = read(fd, buffer + copied,
				rpc_length);
			if (result <= 0) {
					goto close;
			}
			rpc_length -= result;
			copied += result;
			// total_length += result;
			if(rpc_length == 0) {
				rpc_length = flow_size;
				copied = 0;
				// burst -= 1;
				break;
			}
			// if(burst == 0)
			// 	break;
			// return;
		}
		if(is_first == false) {
				is_first = true;
				getcpu(&cpu, &node);
				clock_gettime(CLOCK_MONOTONIC, &first_time);
				printf("%lld.%.9ld core: %d pid: %d port number: %d\n", (long long)first_time.tv_sec, first_time.tv_nsec, cpu,  pid, ntohs(sin.sin_port));
#ifdef SERVER_PRINT_VRUNTIME
				// per-thread start virtual runtime
				std::ostringstream thread_sched_path;
				thread_sched_path << "/proc/" << pid << "/sched";
				std::ifstream sched_file(thread_sched_path.str());
				if (!sched_file.is_open()) {
					printf("Failed to open %s\n", thread_sched_path.str().c_str());
				} else {
					std::string line;
					while (std::getline(sched_file, line)) {
						if (line.find("se.vruntime") != std::string::npos) {
							// format: "se.vruntime                                  :             0.000000"
							std::istringstream iss(line);
							std::string key, colon;
							double vruntime_float;
							long long vruntime;
							if (iss >> key >> colon >> vruntime_float) {
								vruntime = static_cast<long long>(vruntime_float * 1000000); // convert to microseconds
								printf("pid: %d start-vruntime: %lld\n", pid, vruntime);
							} else {
								printf("Failed to parse vruntime line: %s\n", line.c_str());
							}
							break;
						}
					}
					sched_file.close();
				}
#endif
				fflush (stdout);
		}
		copied = 0;
		rpc_length = flow_size;
		// burst = iodepth;
		// if(times == -1)
		// 	break;
		while(1) {
			// if(burst == 1) {
			//	flag = MSG_EOR;
			// } else
			// 	flag = MSG_MORE;
			flag = 0;
			int result = send(fd, buffer + copied,
				rpc_length, flag);

			if (result <= 0) {
					goto close;
			}
			rpc_length -= result;
			copied += result;
			// total_length += result;
			// printf("send rpc\n");
			if(rpc_length == 0) {
				rpc_length = flow_size;
				copied = 0;
				// burst -= 1;
				break;
			}
			// if(burst == 0)
			// 	break;
			// return;
		}
		count++;
	}
		printf( "total len:%" PRIu64 "\n", total_length);
		printf("done!");
	if (verbose)
		printf("Closing TCP socket from %s\n", print_address(&source));
close:
	close(fd);
	printf("Connection closed\n");
	// free(buffer);
}
/**
 * homa_server() - Opens a Homa socket and handles all requests arriving on
 * that socket.
 * @port:   Port number to use for the Homa socket.
 */
// void homa_server(std::string ip, int port)
// {
// 	int fd;
// 	struct sockaddr_in addr_in;
// 	int message[1000000];
// 	struct sockaddr_in source;
// 	int length;
// 	uint64_t total_length = 0, count = 0;
// 	uint64_t start_cycle = 0, end_cycle = 0;
// 	fd = socket(AF_INET, SOCK_DGRAM, IPPROTO_HOMA);
// 	if (fd < 0) {
// 		printf("Couldn't open Homa socket: %s\n", strerror(errno));
// 		return;
// 	}
	
// 	mem(&addr_in, 0, sizeof(addr_in));
// 	addr_in.sin_family = AF_INET;
// 	addr_in.sin_port = htons(port);
// 	inet_pton(AF_INET, ip.c_str(), &addr_in.sin_addr);
// 	// inet_aton("10.0.0.10", &addr_in.sin_addr);
// 	// addr_in.sin_addr.s_addr = INADDR_ANY;

// 	if (bind(fd, (struct sockaddr *) &addr_in, sizeof(addr_in)) != 0) {
// 		printf("Couldn't bind socket to Homa port %d: %s\n", port,
// 				strerror(errno));
// 		return;
// 	}
// 	if (verbose)
// 		printf("Successfully bound to Homa port %d\n", port);
// 	while (1) {
// 		uint64_t id = 0;
// 		int seed;
// 		// int result;
// 		length = homa_recv(fd, message, sizeof(message),
// 			HOMA_RECV_REQUEST, &id, (struct sockaddr *) &source,
// 			sizeof(source));
// 		if (length < 0) {
// 			printf("homa_recv failed: %s\n", strerror(errno));
// 			continue;
// 		}
// 		if (validate) {
// 			seed = check_buffer(&message[2],
// 				length - 2*sizeof32(int));
// 			if (verbose)
// 				printf("Received message from %s with %d bytes, "
// 					"id %lu, seed %d, response length %d\n",
// 					print_address(&source), length, id,
// 					seed, message[1]);
// 		} else
// 			if (verbose)
// 				printf("Received message from %s with "
// 					"%d bytes, id %lu, response length %d\n",
// 					print_address(&source), length, id,
// 					message[1]);
// 		if(count % 1000 == 0) {
// 			end_cycle = rdtsc();
			
// 			double rate = ((double) total_length)/ to_seconds(
// 				end_cycle - start_cycle);
// 			total_length = 0;

// 			start_cycle = rdtsc();
// 			if(count != 0) {
// 				printf("Homa throughput: "
// 				"%.2f Gbps\n", rate * 1e-09 * 8);
// 			}
// 		}
// 		total_length += length;
// 		count += 1;
// 		/* Second word of the message indicates how large a
// 		 * response to send.
// 		 */
// 		// result = homa_reply(fd, message, 1,
// 		// 	(struct sockaddr *) &source, sizeof(source), id);
// 		// if (result < 0) {
// 		// 	printf("Homa_reply failed: %s\n", strerror(errno));
// 		// }
// 	}
// 	printf("end\n");
// }

/**
 * print_help() - Print out usage information for this program.
 * @name:   Name of the program (argv[0])
 */
void print_help(const char *name)
{
	printf("Usage: %s [options]\n\n"
		"The following options are supported:\n\n"
		"--help       Print this message and exit\n"
		"--port       (First) port number to use (default: 4000)\n"
		"--num_ports  Number of Homa ports to open (default: 1)\n"
		"--validate   Validate contents of incoming messages (default: false\n"
		"--verbose    Log events as they happen (default: false)\n",
		name);
}

/**
 * tcp_connection() - Handles messages arriving on a given socket.
 * @fd:           File descriptor for the socket over which messages
 *                will arrive.
 * @client_addr:  Information about the client (for messages).
 */
void tcp_connection(int fd, struct sockaddr_in source)
{
	int flag = 1;
	char buffer[1000000];
	int cur_length = 0;
	bool streaming = false;
	uint64_t count = 0;
	uint64_t total_length = 0;
	uint64_t start_cycle = 0, end_cycle = 0;
	struct sockaddr_in sin;
	socklen_t len = sizeof(sin);
	int *int_buffer = reinterpret_cast<int*>(buffer);
	if (verbose)
		printf("New TCP socket from %s\n", print_address(&source));
	setsockopt(fd, IPPROTO_TCP, TCP_NODELAY, &flag, sizeof(flag));
	if (getsockname(fd, (struct sockaddr *)&sin, &len) == -1)
	    perror("getsockname");
	else
	    printf("port number %d\n", ntohs(sin.sin_port));
	start_cycle = rdtsc();
	while (1) {
		int result = read(fd, buffer + cur_length,
				sizeof(buffer) - cur_length);
		if (result < 0) {
			if (errno == ECONNRESET)
				break;
			printf("Read error on socket: %s", strerror(errno));
			exit(1);
		}
		total_length += result;
		count++;
		if (result == 0)
			break;
		if(count % 1000 == 0) {
			end_cycle = rdtsc();
			
			double rate = ((double) total_length)/ to_seconds(
				end_cycle - start_cycle);
			total_length = 0;

			start_cycle = rdtsc();
			if(count != 0) {
				printf("TCP throughput: "
				"%.2f Gbps\n", rate * 1e-09 * 8);
			}
		}
		/* The connection can be used in two modes. If the first
		 * word received is -1, then the connection is in streaming
		 * mode: we just read bytes and throw them away. If the
		 * first word isn't -1, then it's in message mode: we read
		 * full messages and respond to them.
		 */
		if (streaming)
			continue;
		if (int_buffer[0] < 0) {
			streaming = true;
			continue;
		}
		cur_length += result;

		/* First word of request contains expected length in bytes. */
		if ((cur_length >= 2*sizeof32(int))
				&& (cur_length >= int_buffer[0])) {
			if (cur_length != int_buffer[0])
				printf("Received %d bytes but buffer[0] = %d, "
					"buffer[1] = %d\n",
					cur_length, int_buffer[0],
					int_buffer[1]);
			if (validate) {
				int seed = check_buffer(&int_buffer[2],
					int_buffer[0] - 2*sizeof32(int));
				if (verbose)
					printf("Received message from %s with "
						"%d bytes, seed %d\n",
						print_address(&source),
						int_buffer[0], seed);
			} else if (verbose)
				printf("Received message from %s with %d "
					"bytes\n",
					print_address(&source), int_buffer[0]);
			cur_length = 0;
			if (int_buffer[1] <= 0)
				continue;
			if (write(fd, buffer, int_buffer[1]) != int_buffer[1]) {
				printf("Socket write failed: %s\n",
						strerror(errno));
				exit(1);
			};
		}
	}
	if (verbose)
		printf("Closing TCP socket from %s\n", print_address(&source));
	close(fd);
}

/**
 * tcp_server() - Opens a TCP socket, accepts connections on that socket
 * (one thread per connection) and processes messages on those connections.
 * @port:  Port number on which to listen.
 */
void tcp_server(int port, int num_threads, int iodepth, int flow_size, int pin, int permute, int sc)
{
	int listen_fd = socket(PF_INET, SOCK_STREAM, 0);
 	// std::unique_lock<std::mutex> lk(m,  std::defer_lock);
	int i = 0;
	int conns = 0;
	bool not_created = true;

	if (listen_fd == -1) {
		printf("Couldn't open server socket: %s\n", strerror(errno));
		exit(1);
	}
	int option_value = 1;
	if (setsockopt(listen_fd, SOL_SOCKET, SO_REUSEADDR, &option_value,
			sizeof(option_value)) != 0) {
		printf("Couldn't set SO_REUSEADDR on listen socket: %s",
			strerror(errno));
		exit(1);
	}
	// for (i = 0; i < num_threads; i++) {
	// 	std::thread thread(nd_pingpong);
	// 	if(pin) {
	// 		cpu_set_t cpuset;
	// 		CPU_ZERO(&cpuset);
	// 		CPU_SET(cpu_list[i / threads_per_core], &cpuset);
	// 		pthread_setaffinity_np(thread.native_handle(), sizeof(cpu_set_t), &cpuset);
	// 	}
	//     thread.detach();
	// }
	struct sockaddr_in addr;
	addr.sin_family = AF_INET;
	addr.sin_port = htons(port);
	addr.sin_addr.s_addr = INADDR_ANY;

	if (bind(listen_fd, reinterpret_cast<sockaddr *>(&addr), sizeof(addr))
			== -1) {
		printf("Couldn't bind to port %d: %s\n", port, strerror(errno));
		exit(1);
	}
	if (listen(listen_fd, 1000) == -1) {
		printf("Couldn't listen on socket: %s", strerror(errno));
		exit(1);
	}
	while (1) {
		struct sockaddr_in client_addr;
		socklen_t addr_len = sizeof(client_addr);
		int stream = accept(listen_fd,
				reinterpret_cast<sockaddr *>(&client_addr),
				&addr_len);
		// lk.lock();
		socklist.push_back(Conn_Data(stream, client_addr, iodepth, flow_size));
		// lk.unlock();
		// cv.notify_one();
		if (stream < 0) {
			printf("Couldn't accept incoming connection: %s",
				strerror(errno));
			exit(1);
		}
		conns += 1;
		if(not_created && conns == num_threads) { // bind CPU only after all connections are established
			for (i = 0; i < num_threads; i++) {
				Conn_Data data;
				data = socklist.front();
				socklist.pop_front();
				std::thread thread(nd_pingpong, data.fd, data.source, data.iodepth, data.flow_size);
				std::cout << "thread " << i << " port " << ntohs(data.source.sin_port) << std::endl;
				if(pin == 1) {
					cpu_set_t cpuset;
					CPU_ZERO(&cpuset);
					CPU_SET(sc, &cpuset);
					pthread_setaffinity_np(thread.native_handle(), sizeof(cpu_set_t), &cpuset);
				}
				thread.detach();
			}
			not_created = false;
		}
		i += 1;
	}
}

/**
 * nd_connection() - Handles messages arriving on a given socket.
 * @fd:           File descriptor for the socket over which messages
 *                will arrive.
 * @client_addr:  Information about the client (for messages).
 */
void nd_connection(int fd, struct sockaddr_in source)
{
	// int flag = 1;
	char buffer[9000];
	// int cur_length = 0;
	// bool streaming = false;
	uint64_t count = 0;
	uint64_t total_length = 0;
	// uint64_t start_cycle = 0, end_cycle = 0;
	struct sockaddr_in sin;
	socklen_t len = sizeof(sin);
	// int *int_buffer = reinterpret_cast<int*>(buffer);
	if (verbose)
		printf("New ND socket from %s\n", print_address(&source));
	// setsockopt(fd, IPPROTO_TCP, TCP_NODELAY, &flag, sizeof(flag));
	if (getsockname(fd, (struct sockaddr *)&sin, &len) == -1)
	    perror("getsockname");
	else
	    printf("port number %d\n", ntohs(sin.sin_port));
	// start_cycle = rdtsc();
	printf("start connection\n");
	// printf("sizeof buffer:%ld\n", sizeof(buffer));
	while (1) {
		int result = read(fd, buffer,
				9000);
		// setbuf(stdout, NULL);
		// printf("result:%d\n", result);
		
		// printf("'%.*s'\n", result, buffer);
		// fflush(stdout);
		// while(1) {
					
		// }
		if (result < 0) {
			// if (errno == ECONNRESET)
				break;
		
			// return;
		}
	//	if (total_length <= 8000000)
	//	 	printf("buffer:%s\n", buffer);
		total_length += result;
		count++;
		if (result == 0)
			break;
		std::atomic_fetch_add(&agg_stats.interval_bytes, (unsigned long)result);
		std::atomic_fetch_add(&agg_stats.total_bytes, (unsigned long)result);

		// if(count % 1000 == 0) {
		// 	end_cycle = rdtsc();
		// 	printf("count:%lu\n", count);
		// 	double rate = ((double) total_length)/ to_seconds(
		// 		end_cycle - start_cycle);
		// 	// if(count != 0) {
		// 	// 	printf("ND throughput: "
		// 	// 	"%.2f Gbps, bytes: %f, time: %f\n", rate * 1e-09 * 8, (double) total_length, to_seconds(
		// 	// 	end_cycle - start_cycle));
		// 	// }
		// 	total_length = 0;

		// 	start_cycle = rdtsc();
		// }
		// /* The connection can be used in two modes. If the first
		//  * word received is -1, then the connection is in streaming
		//  * mode: we just read bytes and throw them away. If the
		//  * first word isn't -1, then it's in message mode: we read
		//  * full messages and respond to them.
		//  */
		// if (streaming)
		// 	continue;
		// if (int_buffer[0] < 0) {
		// 	streaming = true;
		// 	continue;
		// }
		// cur_length += result;

		// /* First word of request contains expected length in bytes. */
		// if ((cur_length >= 2*sizeof32(int))
		// 		&& (cur_length >= int_buffer[0])) {
		// 	if (cur_length != int_buffer[0])
		// 		printf("Received %d bytes but buffer[0] = %d, "
		// 			"buffer[1] = %d\n",
		// 			cur_length, int_buffer[0],
		// 			int_buffer[1]);
		// 	if (validate) {
		// 		int seed = check_buffer(&int_buffer[2],
		// 			int_buffer[0] - 2*sizeof32(int));
		// 		if (verbose)
		// 			printf("Received message from %s with "
		// 				"%d bytes, seed %d\n",
		// 				print_address(&source),
		// 				int_buffer[0], seed);
		// 	} else if (verbose)
		// 		printf("Received message from %s with %d "
		// 			"bytes\n",
		// 			print_address(&source), int_buffer[0]);
		// 	cur_length = 0;
		// 	if (int_buffer[1] <= 0)
		// 		continue;
		// 	if (write(fd, buffer, int_buffer[1]) != int_buffer[1]) {
		// 		printf("Socket write failed: %s\n",
		// 				strerror(errno));
		// 		exit(1);
		// 	};
		// }
	}
		printf( "total len:%" PRIu64 "\n", total_length);
		printf("done!");
	if (verbose)
		printf("Closing TCP socket from %s\n", print_address(&source));
	close(fd);
	// free(buffer);
}

/**
 * udp_server()
 *
 */
void udp_server(int port)
{
	char buffer[1000000];
	int result = 0;
	uint64_t start_cycle = 0, end_cycle = 0;
	uint64_t total_length = 0;
	int count = 0;

	int listen_fd = socket(PF_INET, SOCK_DGRAM, 0);
	if (listen_fd == -1) {
		printf("Couldn't open server socket: %s\n", strerror(errno));
		exit(1);
	}
	int option_value = 1;
	if (setsockopt(listen_fd, SOL_SOCKET, SO_REUSEADDR, &option_value,
			sizeof(option_value)) != 0) {
		printf("Couldn't set SO_REUSEADDR on listen socket: %s",
			strerror(errno));
		exit(1);
	}
	struct sockaddr_in addr;
	addr.sin_family = AF_INET;
	addr.sin_port = htons(port);
	addr.sin_addr.s_addr = INADDR_ANY;
	if (bind(listen_fd, reinterpret_cast<sockaddr *>(&addr), sizeof(addr))
			== -1) {
		printf("Couldn't bind to port %d: %s\n", port, strerror(errno));
		exit(1);
	}
	// struct timeval tv;
	// tv.tv_usec = 100 * 1000;
	// if (setsockopt(listen_fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv)))
	// 	return;
	while (1) {
		struct sockaddr_in client_addr;
		socklen_t addr_len = sizeof(client_addr);

		result = recvfrom(listen_fd, (char *)buffer, sizeof(buffer),  
                MSG_WAITALL, ( struct sockaddr *) &client_addr, 
                &addr_len);
		printf("%s\n", buffer);
		printf("%c\n", buffer[10000]);
		if (result < 0) {
			if (errno == ECONNRESET)
				break;
			printf("Read error on socket: %s", strerror(errno));
			exit(1);
		}
		if (result == 0)
			break;
		if(count % 50000 == 0) {
			end_cycle = rdtsc();
			
			double rate = ((double) total_length)/ to_seconds(
				end_cycle - start_cycle);
			total_length = 0;

			start_cycle = rdtsc();
			if(count != 0) {
				printf("UDP throughput: "
				"%.2f Gbps\n", rate * 1e-09 * 8);
			}
		}
		total_length += result;
		count += 1;
	}

}

/**
 * nd_server()
 *
 */
// void nd_server(int port)
// {
// 	// char buffer[1000000];
// 	// int result = 0;
// 	// uint64_t start_cycle = 0, end_cycle = 0;
// 	// uint64_t total_length = 0;
// 	// int count = 0;
// 	int i = 0;
// 	int listen_fd = socket(PF_INET, SOCK_DGRAM, IPPROTO_VIRTUAL_SOCK);
// 	// int listen_fd = socket(PF_INET, SOCK_STREAM, 0);

// 	if (listen_fd == -1) {
// 		printf("Couldn't open server socket: %s\n", strerror(errno));
// 		exit(1);
// 	}
// 	printf("reach here\n");
// 	int option_value = 1;
// 	if (setsockopt(listen_fd, SOL_SOCKET, SO_REUSEADDR | SO_NO_CHECK, &option_value,
// 			sizeof(option_value)) != 0) {
// 		printf("Couldn't set SO_REUSEADDR on listen socket: %s",
// 			strerror(errno));
// 		exit(1);
// 	}
// 	struct sockaddr_in addr;
// 	addr.sin_family = AF_INET;
// 	addr.sin_port = htons(port);
// 	addr.sin_addr.s_addr = INADDR_ANY;
// 	if (bind(listen_fd, reinterpret_cast<sockaddr *>(&addr), sizeof(addr))
// 			== -1) {
// 		printf("Couldn't bind to port %d: %s\n", port, strerror(errno));
// 		exit(1);
// 	}
// 	// struct timeval tv;
// 	// tv.tv_usec = 100 * 1000;
// 	// if (setsockopt(listen_fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv)))
// 	// 	return;
// 	while (1) {
// 		struct sockaddr_in client_addr;
// 		socklen_t addr_len = sizeof(client_addr);
// 		if (listen(listen_fd, 1000) == -1) {
// 			printf("Couldn't listen on socket: %s", strerror(errno));
// 			exit(1);
// 		}
// 		int stream = accept(listen_fd,
// 				reinterpret_cast<sockaddr *>(&client_addr),
// 				&addr_len);
// 		if (stream < 0) {
// 			printf("Couldn't accept incoming connection: %s\n",
// 				strerror(errno));
// 			exit(1);
// 		}
// 		std::thread thread(nd_pingpong, stream, client_addr);

// 		// std::thread thread(nd_connection, stream, client_addr);
// 		cpu_set_t cpuset;
// 		CPU_ZERO(&cpuset);
// 		CPU_SET((i) % 2 * 4, &cpuset);
// 		pthread_setaffinity_np(thread.native_handle(), sizeof(cpu_set_t), &cpuset);
// 		thread.detach();
// 		i += 1;	
// 	}
// 	// while (1) {
// 	// 	struct sockaddr_in client_addr;
// 	// 	socklen_t addr_len = sizeof(client_addr);

// 	// 	result = recvfrom(listen_fd, (char *)buffer, sizeof(buffer),  
//  //                MSG_WAITALL, ( struct sockaddr *) &client_addr, 
//  //                &addr_len);
// 	// 	// printf("%s", buffer);
// 	// 	// printf("%c\n",  buffer[63999]);
// 	// 	// printf("len: %d\n", result);
// 	// 	if (result < 0) {
// 	// 		if (errno == ECONNRESET)
// 	// 			break;
// 	// 		printf("Read error on socket: %s", strerror(errno));
// 	// 		exit(1);
// 	// 	}
// 	// 	if (result == 0)
// 	// 		break;
// 	// 	if(count % 50000 == 0) {
// 	// 		end_cycle = rdtsc();
			
// 	// 		double rate = ((double) total_length)/ to_seconds(
// 	// 			end_cycle - start_cycle);
// 	// 		total_length = 0;

// 	// 		start_cycle = rdtsc();
// 	// 		if(count != 0) {
// 	// 			printf("ND throughput: "
// 	// 			"%.2f Gbps\n", rate * 1e-09 * 8);
// 	// 		}
// 	// 	}
// 	// 	total_length += result;
// 	// 	count += 1;
// 	// }

// }

int main(int argc, char** argv) {
	int next_arg;
	int num_ports = 1;
	int iodepth = 1;
	int flow_size = 64; // bytes
	int pin = 0;
	int permute = 0;
	int sc = 1;
	std::string ip;
	atomic_store(&connected_count, 0);
	if ((argc >= 2) && (strcmp(argv[1], "--help") == 0)) {
		print_help(argv[0]);
		exit(0);
	}
	
	for (next_arg = 1; next_arg < argc; next_arg++) {
		if (strcmp(argv[next_arg], "--help") == 0) {
			print_help(argv[0]);
			exit(0);
		} else if (strcmp(argv[next_arg], "--port") == 0) {
			if (next_arg == (argc-1)) {
				printf("No value provided for %s option\n",
					argv[next_arg]);
				exit(1);
			}
			next_arg++;
			port = get_int(argv[next_arg],
					"Bad port %s; must be positive integer\n");
		} else if (strcmp(argv[next_arg], "--ip") == 0) {
			if (next_arg == (argc-1)) {
				printf("No value provided for %s option\n",
					argv[next_arg]);
				exit(1);
			}
			next_arg++;
			ip = std::string(argv[next_arg]);
		} else if (strcmp(argv[next_arg], "--iodepth") == 0) {
			if (next_arg == (argc-1)) {
				printf("No value provided for %s option\n",
					argv[next_arg]);
				exit(1);
			}
			next_arg++;
			iodepth = get_int(argv[next_arg], 
				"Bad iodepth %s; must be positive integer\n");
		} else if (strcmp(argv[next_arg], "--flowsize") == 0) {
			if (next_arg == (argc-1)) {
				printf("No value provided for %s option\n",
					argv[next_arg]);
				exit(1);
			}
			next_arg++;
			flow_size = get_int(argv[next_arg], 
				"Bad flow size %s; must be positive integer\n");
		} else if (strcmp(argv[next_arg], "--sc") == 0) {
			if (next_arg == (argc-1)) {
				printf("No value provided for %s option\n",
					argv[next_arg]);
				exit(1);
			}
			next_arg++;
			sc = get_int(argv[next_arg], 
				"Bad single core %s; must be positive integer\n");
		} else if (strcmp(argv[next_arg], "--num_ports") == 0) {
			if (next_arg == (argc-1)) {
				printf("No value provided for %s option\n",
					argv[next_arg]);
				exit(1);
			}
			next_arg++;
			num_ports = get_int(argv[next_arg],
				"Bad num_ports %s; must be positive integer\n");
		} else if (strcmp(argv[next_arg], "--validate") == 0) {
			validate = true;
		}else if (strcmp(argv[next_arg], "--pin") == 0) {
			if (next_arg == (argc-1)) {
				printf("No value provided for %s option\n",
					argv[next_arg]);
				exit(1);
			}
			next_arg++;
			pin = get_int(argv[next_arg],
				"pin %s; must be positive integer\n");
		} else if (strcmp(argv[next_arg], "--verbose") == 0) {
			verbose = true;
		}else if (strcmp(argv[next_arg], "--permute") == 0) {
			if (next_arg == (argc-1)) {
				printf("No value provided for %s option\n",
					argv[next_arg]);
				exit(1);
			}
			next_arg++;
			permute = get_int(argv[next_arg], 
				"Bad permute %s; must be positive integer\n");
		}  else if (strcmp(argv[next_arg], "--count") == 0) {
			if (next_arg == (argc-1)) {
				printf("No value provided for %s option\n",
					argv[next_arg]);
				exit(1);
			}
			next_arg++;
			thread_count = get_int(argv[next_arg],
				"Bad num of threads %s; must be positive integer\n");
		}  else {
			printf("Unknown option %s; type '%s --help' for help\n",
				argv[next_arg], argv[0]);
			exit(1);
		}
	}
 	std::vector<std::thread> workers;

	// for (int i = 0; i < num_ports; i++) {
	// 	printf("port number:%i\n", port + i);
	// 	workers.push_back(std::thread (homa_server, ip, port+i));
	// }
	workers.push_back(std::thread(tcp_server, port, thread_count, iodepth, flow_size, pin, permute, sc));

	// workers.push_back(std::thread(udp_server, port));
	// workers.push_back(std::thread(nd_server, port));
	// workers.push_back(std::thread(aggre_thread, &agg_stats));
	for(int i = 0; i < num_ports; i++) {
		workers[i].join();
	}
}

