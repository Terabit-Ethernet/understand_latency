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

// This file contains a collection of tests for the Linux implementation
// of Homa
//
// Usage:
// homaTest host:port [options] op op ...
//
// host:port gives the location of a server to invoke
// Each op specifies a particular test to perform
#include <cassert>
#include <ctime>
#include<chrono>
#include <errno.h>
#include <iostream>
#include <fstream>
#include <netinet/if_ether.h>
#include <netinet/ip.h>
#include <netinet/udp.h>
#include <netdb.h>
#include <netinet/tcp.h>
#include <poll.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <sys/ioctl.h>
#include <sys/types.h>
#include <inttypes.h>
#include <vector>
#include <queue>
#include <thread>
#include <mutex>          // std::mutex
#include <condition_variable> // std::condition_variable

//#include "../uapi_linux_nd.h"
#include "test_utils.h"
#ifndef ETH_MAX_MTU
#define ETH_MAX_MTU	0xFFFFU
#endif

#ifndef UDP_SEGMENT
#define UDP_SEGMENT		103
#endif

/* Determines message size in bytes for tests. */
int length = 1000000;

/* How many iterations to perform for the test. */
int count = 100;

/* Used to generate "somewhat random but predictable" contents for buffers. */
int seed = 12345;

// std::queue<uint64_t> time_q;
std::mutex mtx;           // mutex for critical section
std::condition_variable cv;
int limit = 1024;
// bool queue_available() {return time_q.size() < (long unsigned int)limit;}

/**
 * close_fd() - Helper method for "close" test: sleeps a while, then closes
 * an fd
 * @fd:   Open file descriptor to close.
 */
void close_fd(int fd)
{
	// sleep(1);
	if (close(fd) >= 0) {
		printf("Closed fd %d\n", fd);
	} else {
		printf("Close failed on fd %d: %s\n", fd, strerror(errno));
	}
}

/**
 * print_help() - Print out usage information for this program.
 * @name:   Name of the program (argv[0])
 */
void print_help(const char *name)
{
        printf("Usage: %s host:port [options] op op ...\n\n"
                "host:port describes a server to communicate with, and each op\n"
                "selects a particular test to run (see the code for available\n"
                "tests). The following options are supported:\n\n"
                "--count      Number of times to repeat a test (default: 1000)\n"
                "--length     Size of messages, in bytes (default: 100)\n"
                "--sp       src port of connection \n"
                "--seed       Used to compute message contents (default: 12345)\n",
                name);
}


void test_ndping_send(int fd, struct sockaddr *dest, int id, int io_depth, int flow_size)
{

	std::queue<uint64_t> time_q;
	char *buffer = (char*)malloc(1000000);
	// uint64_t flow_size = 10000000000000;
	int times = 300;
	int flag = 0;
	std::vector<double> latency;
	uint64_t write_len = 0;
	uint64_t start_time = rdtsc();
	uint64_t end = rdtsc();
	uint64_t sent_bytes = 0;
	std::ofstream lfile, tfile;
	
	lfile.open("temp/netperf-" + std::to_string(id)+".log");
	tfile.open("temp/netperf-" + std::to_string(id)+"_thpt.log");
	//int q_depth = 64, count = 0;
	    // for (int i = 0; i < count * 100; i++) {
		/* init burst io_depth packet */
	int total = 0;
	int burst = io_depth;
	while(burst > 0) {
		total = 0;
		time_q.push(rdtsc());
		while(total < flow_size) {
			// if (burst == 1)
			// 	flag = MSG_EOR;
			// else
			// 	flag = MSG_MORE;
		//	printf("send time:%f\n", to_seconds(rdtsc()));
			int result = send(fd, buffer + total, flow_size - total, flag);
			if( result < 0 ) {
				if(errno == EMSGSIZE) {
					printf("Socket write failed: %s %d\n", strerror(errno), result);
					break;
				}
			} else {
				write_len += result;
				total += result;
				sent_bytes += result;	

			}
		}
		burst--;
	}
	while(1) {
		end = rdtsc();
		/* receive one response */
		total = 0;
		while(total < flow_size) {
			int result = read(fd, buffer + total, flow_size - total);	
			if( result < 0 ) {
				if(errno == EMSGSIZE) {
					printf("Socket write failed: %s %d\n", strerror(errno), result);
					break;
				}
			} else {
				total += result;
			}
			if(total == flow_size) {
				uint64_t start = time_q.front();
				end = rdtsc();
				latency.push_back(to_seconds(end - start));
				time_q.pop();
			}
		}
		/* send out one request */
		total = 0;
		time_q.push(rdtsc());
		total = 0;
		while(total < flow_size) {
			int result = send(fd, buffer + total, flow_size - total, flag);
			if( result < 0 ) {
				if(errno == EMSGSIZE) {
					printf("Socket write failed: %s %d\n", strerror(errno), result);
					break;
				}
			} else {
				write_len += result;
				total += result;
				sent_bytes += result;	
			}
		}
		// time_q.push(end);
		if(to_seconds(end-start_time) > times)
			break;
	
	}
	tfile <<   sent_bytes * 8 / to_seconds(end - start_time)  << std::endl;
	for(uint32_t i = 0; i < latency.size(); i++) {
		lfile << "finish time: " << latency[i] << "\n"; 
		// std::cout << "finish time: " << latency[i] << "\n"; 
	}
	lfile.close();
	tfile.close();
	close(fd);
}

// void test_ndping_recv(int fd, struct sockaddr *dest, int id)
// {
// 	//struct sockaddr_in* in = (struct sockaddr_in*) dest;
// 	uint32_t buffer_size = 1000000;
// 	char *buffer = (char*)malloc(1000000);
// 	std::vector<double> latency;
// 	std::ofstream file;
// 	file.open("result_tcp_pingpongasync_" + std::to_string(id));
// 	int times = 70;
// 	uint64_t write_len = 0;
// 	uint64_t start_time = rdtsc();
// 	uint64_t remain = 0;
// 	while(1) {
// 		int result = read(fd, buffer, buffer_size);
// 		if( result < 0 ) {
// 			if(errno == EMSGSIZE) {
// 				break;
// 			}
// 		} else {
// 			write_len += result;
// 			remain += result;
// 		}
// 		while(remain >= 1024) {
// 			std::unique_lock<std::mutex> lck(mtx);
// 			uint64_t end = rdtsc();
// 			uint64_t start = time_q.front();
// 			if(time_q.empty())
// 				assert(false);	
// 			latency.push_back(to_seconds(end - start));
// 			time_q.pop();
// 			remain -= 1024;
// 			cv.notify_one();
// 		}
// 		uint64_t end = rdtsc();
// 		if(to_seconds(end-start_time) > times)
// 			break;
// 	}
// 	printf("finish\n");
// 	for(uint32_t i = 0; i < latency.size(); i++) {
// 		file << "finish time: " << latency[i] << "\n"; 
// 		// std::cout << "finish time: " << latency[i] << "\n"; 
// 	}
// 	file.close();

// }
/**
 * tcp_pingping() - Handles messages arriving on a given socket.
 * @fd:           File descriptor for the socket over which messages
 *                will arrive.
 * @client_addr:  Information about the client (for messages).
 */
void test_tcppingpong(int fd, struct sockaddr *dest, int id)
{
	// int flag = 1;
	int times = 90;
	char buffer[5000];
	std::ofstream file;
	file.open("result_tcp_pingpong_"+ std::to_string(id));
	// int cur_length = 0;
	// bool streaming = false;
	uint64_t count = 0;
	// uint64_t total_length = 0;
	uint64_t start_time;
	std::vector<double> latency;
	printf("reach here1\n");
	if (connect(fd, dest, sizeof(struct sockaddr_in)) == -1) {
		printf("Couldn't connect to dest %s\n", strerror(errno));
		exit(1);
	}
	start_time = rdtsc();
	while (1) {
		int copied = 0;
		int rpc_length = 4096;
		// times--;
		// if(times == 0)
		// 	break;
		uint64_t start = rdtsc(), end;
		while(1) {
			int result = write(fd, buffer + copied,
				rpc_length);
			if (result <= 0) {
				printf("goto close\n");
					goto close;
			}
			rpc_length -= result;
			copied += result;
			if(rpc_length == 0)
				break;
			// return;
		}
		copied = 0;
		rpc_length = 4096;
		while(1) {
			int result = read(fd, buffer + copied,
				rpc_length);
			if (result <= 0) {
					printf("goto close2\n");
					goto close;
			}
			// printf("result:%d\n",result);
			// printf("receive rpc times:%d \n", times);
			rpc_length -= result;
			copied += result;
			if(rpc_length == 0)
				break;
			// return;
		}
		end = rdtsc();
		latency.push_back(to_seconds(end-start));
		// printf("finsh time: %f cycles:%lu\n",  to_seconds(end-start), end-start);
		if(to_seconds(end-start_time) > times)
			break;
	//	if (total_length <= 8000000)
	//	 	printf("buffer:%s\n", buffer);
		count++;

	}
		// printf( "total len:%" PRIu64 "\n", total_length);
		// printf("done!");
close:
	sleep(10);

	for(uint32_t i = 0; i < latency.size(); i++) {
		file << "finish time: " << latency[i] << "\n"; 
		// std::cout << "finish time: " << latency[i] << "\n"; 
	}
	file.close();
	close(fd);
	return;
}

/**
 * nd_pingping() - Handles messages arriving on a given socket.
 * @fd:           File descriptor for the socket over which messages
 *                will arrive.
 * @client_addr:  Information about the client (for messages).
 */
void test_ndpingpong(int fd, struct sockaddr *dest, int id)
{
	// int flag = 1;
	int times = 90;
	// int cur_length = 0;
	// bool streaming = false;
	uint64_t count = 0;
	// uint64_t total_length = 0;
	char buffer[5000];
	std::ofstream file;
	file.open("result_nd_pingpong_"+ std::to_string(id));
	uint64_t start_time;
	std::vector<double> latency;
	printf("reach here1\n");
	if (connect(fd, dest, sizeof(struct sockaddr_in)) == -1) {
		printf("Couldn't connect to dest %s\n", strerror(errno));
		exit(1);
	}
	start_time = rdtsc();
	while (1) {
		int copied = 0;
		int rpc_length = 4096;
		// times--;
		// if(times == 0)
		// 	break;
		uint64_t start = rdtsc(), end;
		while(1) {
			int result = write(fd, buffer + copied,
				rpc_length);
			if (result <= 0) {
				printf("goto close\n");
					goto close;
			}
			rpc_length -= result;
			copied += result;
			if(rpc_length == 0)
				break;
			// return;
		}
		copied = 0;
		rpc_length = 4096;
		while(1) {
			int result = read(fd, buffer + copied,
				rpc_length);
			if (result <= 0) {
					printf("goto close2\n");
					goto close;
			}
			// printf("result:%d\n",result);
			// printf("receive rpc times:%d \n", times);
			rpc_length -= result;
			copied += result;
			if(rpc_length == 0)
				break;
			// return;
		}
		end = rdtsc();
		latency.push_back(to_seconds(end-start));
		// printf("finsh time: %f cycles:%lu\n",  to_seconds(end-start), end-start);
		if(to_seconds(end-start_time) > times)
			break;
	//	if (total_length <= 8000000)
	//	 	printf("buffer:%s\n", buffer);
		count++;

	}
		// printf( "total len:%" PRIu64 "\n", total_length);
		// printf("done!");
close:
	sleep(10);
	for(uint32_t i = 0; i < latency.size(); i++) {
		file << "finish time: " << latency[i] << "\n"; 
		// std::cout << "finish time: " << latency[i] << "\n"; 
	}
	file.close();
	close(fd);
	return;
}


int main(int argc, char** argv)
{
	int port, nextArg, tempArg, optval;
	unsigned optlen;
	struct sockaddr_in addr_in;
	struct addrinfo *matching_addresses;
	struct sockaddr *dest;
	struct addrinfo hints;
	char *host, *port_name;
 	std::vector<std::thread> workers;
	// char buffer[8000000] = "abcdefgh\n";
	char *buffer = (char*)malloc(10000000);
	int flow_size = 64;
	// buffer[63999] = 'H';
	int status;
	int fd;
	int i;
	int srcPort = 0;
	int io_depth = 1;
	if ((argc >= 2) && (strcmp(argv[1], "--help") == 0)) {
		print_help(argv[0]);
		exit(0);
	}
	for (i = 0; i < 8000000; i++)
		buffer[i] = (rand()) % 26 + 'a';
//	printf("buffer:%s\n", buffer);
	if (argc < 3) {
		printf("Usage: %s host:port [options] op op ...\n", argv[0]);
		exit(1);
	}
	host = argv[1];
	port_name = strchr(argv[1], ':');
	if (port_name == NULL) {
		printf("Bad server spec %s: must be 'host:port'\n", argv[1]);
		exit(1);
	}
	*port_name = 0;
	port_name++;
	port = get_int(port_name,
			"Bad port number %s; must be positive integer\n");
	for (nextArg = 2; (nextArg < argc) && (*argv[nextArg] == '-');
			nextArg += 1) {
		if (strcmp(argv[nextArg], "--help") == 0) {
			print_help(argv[0]);
			exit(0);
		} else if (strcmp(argv[nextArg], "--count") == 0) {
			if (nextArg == (argc-1)) {
				printf("No value provided for %s option\n",
					argv[nextArg]);
				exit(1);
			}
			nextArg++;
			count = get_int(argv[nextArg],
					"Bad count %s; must be positive integer\n");
		} else if (strcmp(argv[nextArg], "--length") == 0) {
			if (nextArg == (argc-1)) {
				printf("No value provided for %s option\n",
					argv[nextArg]);
				exit(1);
			}
			nextArg++;
			length = get_int(argv[nextArg],
				"Bad message length %s; must be positive "
				"integer\n");
			if (length > 1000000) {
				length = 1000000;
				printf("Reducing message length to %d\n", length);
			}
		} else if (strcmp(argv[nextArg], "--sp") == 0) {
			if (nextArg == (argc-1)) {
				printf("No value provided for %s option\n",
					argv[nextArg]);
				exit(1);
			}
			nextArg++;
			srcPort = get_int(argv[nextArg],
				"Bad srcPort %s; must be positive integer\n");
		} else if (strcmp(argv[nextArg], "--limit") == 0) {
			if (nextArg == (argc-1)) {
				printf("No value provided for %s option\n",
					argv[nextArg]);
				exit(1);
			}
			nextArg++;
			limit = get_int(argv[nextArg],
				"Bad limit %s; must be positive integer\n");
		} else if (strcmp(argv[nextArg], "--iodepth") == 0) {
			if (nextArg == (argc-1)) {
				printf("No value provided for %s option\n",
					argv[nextArg]);
				exit(1);
			}
			nextArg++;
			io_depth = get_int(argv[nextArg],
				"Bad io_depth %s; must be positive integer\n");
		} else if (strcmp(argv[nextArg], "--flowsize") == 0){
			if (nextArg == (argc-1)) {
				printf("No value provided for %s option\n",
					argv[nextArg]);
				exit(1);
			}
			nextArg++;
			flow_size = get_int(argv[nextArg],
				"Bad flow size %s; must be positive integer\n");
			std::cout << "flow size:" << flow_size << std::endl;
		} else {
			printf("Unknown option %s; type '%s --help' for help\n",
				argv[nextArg], argv[0]);
			exit(1);
		}
	}
	// get destination address
	memset(&hints, 0, sizeof(struct addrinfo));
	hints.ai_family = AF_INET;
	hints.ai_socktype = SOCK_DGRAM;
	status = getaddrinfo(host, "80", &hints, &matching_addresses);
	if (status != 0) {
		printf("Couldn't look up address for %s: %s\n",
				host, gai_strerror(status));
		exit(1);
	}
	dest = matching_addresses->ai_addr;
	((struct sockaddr_in *) dest)->sin_port = htons(port);
	// int *ibuf = reinterpret_cast<int *>(buffer);
	// ibuf[0] = ibuf[1] = length;
	// seed_buffer(&ibuf[2], sizeof32(buffer) - 2*sizeof32(int), seed);
	tempArg = nextArg;
	for(i = 0; i < count; i++) {
		nextArg = tempArg;
		memset(&addr_in, 0, sizeof(addr_in));
		addr_in.sin_family = AF_INET;
		addr_in.sin_port = htons(srcPort + i);
		addr_in.sin_addr.s_addr = inet_addr("192.168.10.125");


		// if (bind(fd, (struct sockaddr *) &addr_in, sizeof(addr_in)) != 0) {
		// 	printf("Couldn't bind socket to ND port %d: %s\n", port,
		// 			strerror(errno));
		// 	return -1;
		// }

		for ( ; nextArg < argc; nextArg++) {
			if (strcmp(argv[nextArg], "tcpppasync") == 0) {
				fd = socket(AF_INET, SOCK_STREAM, 0);
				if (connect(fd, dest, sizeof(struct sockaddr_in)) == -1) {
					printf("Couldn't connect to dest %s\n", strerror(errno));
					exit(1);
				}
				workers.push_back(std::thread(test_ndping_send, fd, dest, i, io_depth, flow_size));
				// cpu_set_t cpuset;
				// CPU_ZERO(&cpuset);
				// CPU_SET((i) % 16 * 4, &cpuset);
				// pthread_setaffinity_np(workers[workers.size() - 1].native_handle(), sizeof(cpu_set_t), &cpuset);
				
				//workers.push_back(std::thread(test_ndping_recv, fd, dest, srcPort - 10000));
			} else if (strcmp(argv[nextArg], "tcppingpong") == 0) {
				fd = socket(AF_INET, SOCK_STREAM, 0);
				optval = 6;
				setsockopt(fd, SOL_SOCKET, SO_PRIORITY, &optval, unsigned(sizeof(optval)));  
				getsockopt(fd, SOL_SOCKET, SO_PRIORITY, &optval, &optlen);
				printf("optval:%d\n", optval);
				workers.push_back(std::thread(test_tcppingpong, fd, dest, i));
			} 
			 else {
				printf("Unknown operation '%s'\n", argv[nextArg]);
				exit(1);
			}
		}
	}
       std::this_thread::sleep_for (std::chrono::seconds(100));

	for(unsigned i = 0; i < workers.size(); i++) {
		workers[i].join();
	}
	free(buffer);
	exit(0);
}

