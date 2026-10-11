package fonts

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"os"
	"path"
)

func randomToken() (string, error) {
	var bytes [24]byte
	if _, err := rand.Read(bytes[:]); err != nil {
		return "", err
	}
	return hex.EncodeToString(bytes[:]), nil
}
func digest(bytes []byte) string { sum := sha256.Sum256(bytes); return hex.EncodeToString(sum[:]) }
func (s *Service) openRoot() (*os.Root, error) {
	if err := os.MkdirAll(s.mediaDir, 0755); err != nil {
		return nil, err
	}
	return os.OpenRoot(s.mediaDir)
}
func (s *Service) writeBlob(relative string, data []byte) error {
	root, err := s.openRoot()
	if err != nil {
		return err
	}
	defer root.Close()
	if err := root.MkdirAll(path.Dir(relative), 0755); err != nil {
		return err
	}
	token, err := randomToken()
	if err != nil {
		return err
	}
	temp := relative + ".tmp-" + token
	file, err := root.OpenFile(temp, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0644)
	if err != nil {
		return err
	}
	defer root.Remove(temp)
	if _, err := file.Write(data); err != nil {
		file.Close()
		return err
	}
	if err := file.Sync(); err != nil {
		file.Close()
		return err
	}
	if err := file.Close(); err != nil {
		return err
	}
	return root.Rename(temp, relative)
}
