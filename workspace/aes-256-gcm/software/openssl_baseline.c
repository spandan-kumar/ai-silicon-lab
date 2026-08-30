#define _POSIX_C_SOURCE 200809L

#include <errno.h>
#include <openssl/crypto.h>
#include <openssl/evp.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define MAX_BYTES 64

static int hex_nibble(char value) {
    if (value >= '0' && value <= '9') return value - '0';
    if (value >= 'a' && value <= 'f') return value - 'a' + 10;
    if (value >= 'A' && value <= 'F') return value - 'A' + 10;
    return -1;
}

static int decode_hex(const char *text, uint8_t *output, size_t capacity, size_t *length) {
    size_t characters = strlen(text);
    if ((characters & 1u) != 0 || characters / 2 > capacity) return 0;
    *length = characters / 2;
    for (size_t i = 0; i < *length; ++i) {
        int high = hex_nibble(text[2 * i]);
        int low = hex_nibble(text[2 * i + 1]);
        if (high < 0 || low < 0) return 0;
        output[i] = (uint8_t)((high << 4) | low);
    }
    return 1;
}

static void print_hex(const uint8_t *data, size_t length) {
    for (size_t i = 0; i < length; ++i) printf("%02x", data[i]);
}

static int encrypt_gcm(const uint8_t key[32], const uint8_t *iv, size_t iv_length,
                       const uint8_t *aad, size_t aad_length, const uint8_t *plaintext,
                       size_t plaintext_length, uint8_t *ciphertext, uint8_t tag[16]) {
    EVP_CIPHER_CTX *context = EVP_CIPHER_CTX_new();
    int length = 0;
    int total = 0;
    int ok = context != NULL
        && EVP_EncryptInit_ex(context, EVP_aes_256_gcm(), NULL, NULL, NULL) == 1
        && EVP_CIPHER_CTX_ctrl(context, EVP_CTRL_GCM_SET_IVLEN, (int)iv_length, NULL) == 1
        && EVP_EncryptInit_ex(context, NULL, NULL, key, iv) == 1;
    if (ok && aad_length != 0)
        ok = EVP_EncryptUpdate(context, NULL, &length, aad, (int)aad_length) == 1;
    if (ok && plaintext_length != 0) {
        ok = EVP_EncryptUpdate(context, ciphertext, &length, plaintext, (int)plaintext_length) == 1;
        total = length;
    }
    if (ok) ok = EVP_EncryptFinal_ex(context, ciphertext + total, &length) == 1;
    if (ok) ok = EVP_CIPHER_CTX_ctrl(context, EVP_CTRL_GCM_GET_TAG, 16, tag) == 1;
    EVP_CIPHER_CTX_free(context);
    return ok;
}

static int decrypt_gcm(const uint8_t key[32], const uint8_t *iv, size_t iv_length,
                       const uint8_t *aad, size_t aad_length, const uint8_t *ciphertext,
                       size_t ciphertext_length, const uint8_t tag[16], uint8_t *plaintext) {
    EVP_CIPHER_CTX *context = EVP_CIPHER_CTX_new();
    int length = 0;
    int total = 0;
    int ok = context != NULL
        && EVP_DecryptInit_ex(context, EVP_aes_256_gcm(), NULL, NULL, NULL) == 1
        && EVP_CIPHER_CTX_ctrl(context, EVP_CTRL_GCM_SET_IVLEN, (int)iv_length, NULL) == 1
        && EVP_DecryptInit_ex(context, NULL, NULL, key, iv) == 1;
    if (ok && aad_length != 0)
        ok = EVP_DecryptUpdate(context, NULL, &length, aad, (int)aad_length) == 1;
    if (ok && ciphertext_length != 0) {
        ok = EVP_DecryptUpdate(context, plaintext, &length, ciphertext, (int)ciphertext_length) == 1;
        total = length;
    }
    if (ok) ok = EVP_CIPHER_CTX_ctrl(context, EVP_CTRL_GCM_SET_TAG, 16, (void *)tag) == 1;
    if (ok) ok = EVP_DecryptFinal_ex(context, plaintext + total, &length) == 1;
    EVP_CIPHER_CTX_free(context);
    if (!ok) memset(plaintext, 0, ciphertext_length);
    return ok;
}

static int process_vectors(void) {
    char line[2048];
    uint8_t key[32], iv[16], aad[MAX_BYTES], input[MAX_BYTES], tag[16], output[MAX_BYTES];
    while (fgets(line, sizeof(line), stdin) != NULL) {
        line[strcspn(line, "\r\n")] = '\0';
        char *fields[6] = {0};
        size_t count = 0;
        for (char *token = strtok(line, "\t"); token != NULL && count < 6; token = strtok(NULL, "\t"))
            fields[count++] = token;
        if (count < 5) {
            fprintf(stderr, "malformed request\n");
            return 2;
        }
        size_t key_len, iv_len, aad_len, input_len, tag_len = 0;
        if (!decode_hex(fields[1], key, sizeof(key), &key_len) || key_len != 32
            || !decode_hex(fields[2], iv, sizeof(iv), &iv_len)
            || !decode_hex(strcmp(fields[3], "-") == 0 ? "" : fields[3], aad, sizeof(aad), &aad_len)
            || !decode_hex(strcmp(fields[4], "-") == 0 ? "" : fields[4], input, sizeof(input), &input_len)) {
            fprintf(stderr, "invalid hex or length\n");
            return 2;
        }
        if (strcmp(fields[0], "E") == 0) {
            if (!encrypt_gcm(key, iv, iv_len, aad, aad_len, input, input_len, output, tag)) return 3;
            printf("P\t"); print_hex(output, input_len); printf("\t"); print_hex(tag, sizeof(tag)); printf("\n");
        } else if (strcmp(fields[0], "D") == 0 && count == 6
                   && decode_hex(fields[5], tag, sizeof(tag), &tag_len) && tag_len == 16) {
            if (decrypt_gcm(key, iv, iv_len, aad, aad_len, input, input_len, tag, output)) {
                printf("P\t"); print_hex(output, input_len); printf("\n");
            } else {
                printf("F\n");
            }
        } else {
            fprintf(stderr, "invalid operation\n");
            return 2;
        }
    }
    return ferror(stdin) ? 4 : 0;
}

static uint64_t elapsed_ns(struct timespec start, struct timespec end) {
    return (uint64_t)(end.tv_sec - start.tv_sec) * UINT64_C(1000000000)
        + (uint64_t)(end.tv_nsec - start.tv_nsec);
}

static int benchmark(void) {
    static const size_t lengths[] = {0, 1, 15, 16, 17, 31, 32, 64};
    uint8_t key[32], iv[12], aad[MAX_BYTES], input[MAX_BYTES], output[MAX_BYTES], tag[16];
    for (size_t i = 0; i < sizeof(key); ++i) key[i] = (uint8_t)(3 * i + 1);
    for (size_t i = 0; i < sizeof(iv); ++i) iv[i] = (uint8_t)(5 * i + 2);
    for (size_t i = 0; i < sizeof(aad); ++i) aad[i] = (uint8_t)(7 * i + 3);
    for (size_t i = 0; i < sizeof(input); ++i) input[i] = (uint8_t)(11 * i + 4);
    puts("payload_bytes,aad_bytes,iterations,total_ns,ns_per_transaction,ns_per_payload_byte");
    for (size_t index = 0; index < sizeof(lengths) / sizeof(lengths[0]); ++index) {
        size_t payload_length = lengths[index];
        size_t aad_length = lengths[sizeof(lengths) / sizeof(lengths[0]) - 1 - index];
        unsigned iterations = payload_length < 16 ? 200000u : 100000u;
        struct timespec start, end;
        if (clock_gettime(CLOCK_MONOTONIC, &start) != 0) return errno;
        for (unsigned run = 0; run < iterations; ++run) {
            iv[11] = (uint8_t)run;
            if (!encrypt_gcm(key, iv, sizeof(iv), aad, aad_length, input, payload_length, output, tag)) return 3;
        }
        if (clock_gettime(CLOCK_MONOTONIC, &end) != 0) return errno;
        uint64_t ns = elapsed_ns(start, end);
        double per_transaction = (double)ns / iterations;
        double per_byte = payload_length == 0 ? 0.0 : per_transaction / payload_length;
        printf("%zu,%zu,%u,%llu,%.3f,%.3f\n", payload_length, aad_length, iterations,
               (unsigned long long)ns, per_transaction, per_byte);
    }
    return 0;
}

int main(int argc, char **argv) {
    if (argc == 2 && strcmp(argv[1], "--version") == 0) {
        puts(OpenSSL_version(OPENSSL_VERSION));
        return 0;
    }
    if (argc == 2 && strcmp(argv[1], "--benchmark") == 0) return benchmark();
    if (argc != 1) {
        fprintf(stderr, "usage: %s [--benchmark|--version]\n", argv[0]);
        return 2;
    }
    return process_vectors();
}
