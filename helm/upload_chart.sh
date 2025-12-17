rm -rf ./tmp
mkdir ./tmp
cd ./tmp
helm package ../krr-enforcer
mkdir krr-enforcer
mv *.tgz ./krr-enforcer
curl https://robusta-charts.storage.googleapis.com/index.yaml > index.yaml
helm repo index --merge index.yaml --url https://robusta-charts.storage.googleapis.com ./krr-enforcer
gsutil rsync -r krr-enforcer gs://robusta-charts
gsutil setmeta -h "Cache-Control:max-age=0" gs://robusta-charts/index.yaml
cd ../
rm -rf ./tmp


hi
