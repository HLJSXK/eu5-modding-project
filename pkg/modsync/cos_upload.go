package modsync

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strings"

	cos "github.com/tencentyun/cos-go-sdk-v5"
)

func uploadPublishOutputToCOS(opts PublishOptions, manifestPath, packagesDir string) error {
	if opts.Out != nil {
		fmt.Fprintf(opts.Out, "COS target: bucket=%s region=%s prefix=%s\n", opts.COSBucket, opts.COSRegion, normalizeCOSPrefix(opts.COSPrefix))
	}

	client, err := newCOSClient(opts.COSBucket, opts.COSRegion, opts.COSSecretID, opts.COSSecretKey)
	if err != nil {
		return err
	}

	prefix := normalizeCOSPrefix(opts.COSPrefix)

	manifestKey := prefix + "snapshot.json"
	if opts.Out != nil {
		fmt.Fprintf(opts.Out, "Uploading %s -> %s\n", manifestPath, manifestKey)
	}
	if err := putFileToCOS(client, manifestKey, manifestPath); err != nil {
		return fmt.Errorf("failed to upload snapshot.json: %w", err)
	}

	b, err := os.ReadFile(manifestPath)
	if err != nil {
		return fmt.Errorf("failed to read snapshot manifest: %w", err)
	}
	var manifest SnapshotManifest
	if err := json.Unmarshal(b, &manifest); err != nil {
		return fmt.Errorf("failed to parse snapshot manifest: %w", err)
	}

	for _, mod := range manifest.Mods {
		zipName := mod.ModID + ".zip"
		localPath := filepath.Join(packagesDir, zipName)
		if _, err := os.Stat(localPath); err != nil {
			return fmt.Errorf("missing package for mod %s: %w", mod.ModID, err)
		}
		objectKey := prefix + "packages/" + zipName
		if opts.Out != nil {
			fmt.Fprintf(opts.Out, "Uploading %s -> %s\n", localPath, objectKey)
		}
		if err := putFileToCOS(client, objectKey, localPath); err != nil {
			return fmt.Errorf("failed to upload package %s: %w", zipName, err)
		}
	}

	return nil
}

func newCOSClient(bucket, region, secretID, secretKey string) (*cos.Client, error) {
	bucketURL, err := url.Parse(fmt.Sprintf("https://%s.cos.%s.myqcloud.com", bucket, region))
	if err != nil {
		return nil, fmt.Errorf("failed to build COS bucket URL: %w", err)
	}
	baseURL := &cos.BaseURL{BucketURL: bucketURL}
	return cos.NewClient(baseURL, &http.Client{
		Transport: &cos.AuthorizationTransport{
			SecretID:  secretID,
			SecretKey: secretKey,
		},
	}), nil
}

func putFileToCOS(client *cos.Client, objectKey, localPath string) error {
	f, err := os.Open(localPath)
	if err != nil {
		return err
	}
	defer f.Close()

	_, err = client.Object.Put(contextWithProgress(), objectKey, f, nil)
	return err
}

func normalizeCOSPrefix(prefix string) string {
	p := strings.TrimSpace(prefix)
	p = strings.Trim(p, "/")
	if p == "" {
		return ""
	}
	return p + "/"
}

func buildCOSPublicBaseURL(bucket, region, prefix string) string {
	base := fmt.Sprintf("https://%s.cos.%s.myqcloud.com", bucket, region)
	p := normalizeCOSPrefix(prefix)
	if p == "" {
		return base
	}
	return base + "/" + strings.TrimRight(p, "/")
}

func contextWithProgress() context.Context {
	return context.Background()
}
