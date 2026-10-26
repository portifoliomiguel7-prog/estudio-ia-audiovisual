param([Parameter(Mandatory=$true)][string]$JobFile)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Speech
$job = Get-Content -LiteralPath $JobFile -Raw -Encoding UTF8 | ConvertFrom-Json
$synth = [System.Speech.Synthesis.SpeechSynthesizer]::new()
try {
  $synth.SelectVoice($job.voice)
  $synth.Rate = [int]$job.rate
  $synth.Volume = 100
  foreach ($item in $job.items) {
    $format = [System.Speech.AudioFormat.SpeechAudioFormatInfo]::new(48000,[System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen,[System.Speech.AudioFormat.AudioChannel]::Mono)
    $synth.SetOutputToWaveFile($item.output,$format)
    $synth.Speak([string]$item.text)
    $synth.SetOutputToNull()
  }
} finally { $synth.Dispose() }
