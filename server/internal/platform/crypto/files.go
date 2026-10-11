package crypto

import (
	"context"
	"crypto/aes"
	"crypto/cipher"
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/base64"
	"encoding/binary"
	"errors"
	"io"
	"os"
	"path/filepath"
	"time"
)

// EncryptFile writes the same Fernet token as legacy core/offsite.py, in
// bounded memory. Atomic replacement is used only for the caller's staging
// destination; the source archive is never altered.
func EncryptFile(ctx context.Context, key, source, target string) error {
	if key == "" {
		return errors.New("没有设置 BACKUP_ENCRYPTION_KEY，不能上传未加密的备份。")
	}
	signing, encryption, err := splitKey(key)
	if err != nil {
		return err
	}
	input, err := os.Open(source)
	if err != nil {
		return err
	}
	defer input.Close()
	info, err := input.Stat()
	if err != nil {
		return err
	}
	if !info.Mode().IsRegular() {
		return errors.New("备份源不是普通文件。")
	}
	stage, err := os.CreateTemp(filepath.Dir(target), ".encrypted-*")
	if err != nil {
		return err
	}
	name := stage.Name()
	defer os.Remove(name)
	defer stage.Close()
	if err := stage.Chmod(0600); err != nil {
		return err
	}
	encoder := base64.NewEncoder(base64.URLEncoding, stage)
	mac := hmac.New(sha256.New, signing)
	writer := io.MultiWriter(encoder, mac)
	header := make([]byte, 25)
	header[0] = 0x80
	binary.BigEndian.PutUint64(header[1:9], uint64(time.Now().Unix()))
	if _, err := rand.Read(header[9:]); err != nil {
		return err
	}
	if _, err := writer.Write(header); err != nil {
		return err
	}
	block, err := aes.NewCipher(encryption)
	if err != nil {
		return err
	}
	cbc := cipher.NewCBCEncrypter(block, header[9:])
	buffer := make([]byte, 64*1024)
	for {
		if err := ctx.Err(); err != nil {
			return err
		}
		n, readErr := io.ReadFull(input, buffer)
		if readErr != nil && readErr != io.EOF && readErr != io.ErrUnexpectedEOF {
			return readErr
		}
		if readErr == nil {
			cbc.CryptBlocks(buffer, buffer)
			if _, err := writer.Write(buffer); err != nil {
				return err
			}
			continue
		}
		// Even an exact block-boundary source gets one whole padding block.
		padded := pkcs7Pad(buffer[:n], aes.BlockSize)
		cbc.CryptBlocks(padded, padded)
		if _, err := writer.Write(padded); err != nil {
			return err
		}
		break
	}
	if _, err := encoder.Write(mac.Sum(nil)); err != nil {
		return err
	}
	if err := encoder.Close(); err != nil {
		return err
	}
	if err := stage.Sync(); err != nil {
		return err
	}
	if err := stage.Close(); err != nil {
		return err
	}
	return os.Rename(name, target)
}

// DecryptFile authenticates the entire token before creating plaintext. A
// tampered or truncated backup therefore never replaces an existing target.
func DecryptFile(ctx context.Context, key, source, target string) error {
	if key == "" {
		return errors.New("没有设置 BACKUP_ENCRYPTION_KEY，无法解密备份。")
	}
	signing, encryption, err := splitKey(key)
	if err != nil {
		return err
	}
	token, err := os.Open(source)
	if err != nil {
		return err
	}
	defer token.Close()
	raw, err := os.CreateTemp(filepath.Dir(target), ".fernet-ciphertext-*")
	if err != nil {
		return err
	}
	rawName := raw.Name()
	defer os.Remove(rawName)
	defer raw.Close()
	if err := raw.Chmod(0600); err != nil {
		return err
	}
	reader := base64.NewDecoder(base64.URLEncoding, token)
	buffer := make([]byte, 64*1024)
	for {
		if err := ctx.Err(); err != nil {
			return err
		}
		n, readErr := reader.Read(buffer)
		if n > 0 {
			if _, err := raw.Write(buffer[:n]); err != nil {
				return err
			}
		}
		if readErr == io.EOF {
			break
		}
		if readErr != nil {
			return errBad
		}
	}
	size, err := raw.Seek(0, io.SeekCurrent)
	if err != nil {
		return err
	}
	if size < 73 || (size-25-sha256.Size)%aes.BlockSize != 0 {
		return errBad
	}
	if _, err := raw.Seek(0, io.SeekStart); err != nil {
		return err
	}
	mac := hmac.New(sha256.New, signing)
	if _, err := io.CopyN(mac, raw, size-sha256.Size); err != nil {
		return errBad
	}
	signature := make([]byte, sha256.Size)
	if _, err := io.ReadFull(raw, signature); err != nil {
		return errBad
	}
	if subtle.ConstantTimeCompare(mac.Sum(nil), signature) != 1 {
		return errBad
	}
	if _, err := raw.Seek(0, io.SeekStart); err != nil {
		return err
	}
	header := make([]byte, 25)
	if _, err := io.ReadFull(raw, header); err != nil || header[0] != 0x80 {
		return errBad
	}
	block, err := aes.NewCipher(encryption)
	if err != nil {
		return err
	}
	cbc := cipher.NewCBCDecrypter(block, header[9:])
	plain, err := os.CreateTemp(filepath.Dir(target), ".decrypted-*")
	if err != nil {
		return err
	}
	name := plain.Name()
	defer os.Remove(name)
	defer plain.Close()
	if err := plain.Chmod(0600); err != nil {
		return err
	}
	remaining := size - 25 - sha256.Size
	for remaining > 0 {
		if err := ctx.Err(); err != nil {
			return err
		}
		count := int64(len(buffer))
		if count > remaining {
			count = remaining
		}
		chunk := buffer[:int(count)]
		if _, err := io.ReadFull(raw, chunk); err != nil {
			return errBad
		}
		cbc.CryptBlocks(chunk, chunk)
		remaining -= count
		if remaining == 0 {
			chunk, err = pkcs7Unpad(chunk, aes.BlockSize)
			if err != nil {
				return errBad
			}
		}
		if _, err := plain.Write(chunk); err != nil {
			return err
		}
	}
	if err := plain.Sync(); err != nil {
		return err
	}
	if err := plain.Close(); err != nil {
		return err
	}
	return os.Rename(name, target)
}
